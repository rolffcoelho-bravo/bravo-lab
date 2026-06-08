"""
Regime and stress-window diagnostics for BRAVO Lab.

This module evaluates whether overlay strategies work when they matter most:
during fragile, stress, and extreme-stress market regimes.

The purpose is to move beyond full-sample performance and test the decision
logic under market pressure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def align_regime_to_strategy_dates(
    strategy_returns: pd.DataFrame,
    regime: pd.Series,
) -> pd.Series:
    """
    Align daily regime labels to strategy return dates.

    The overlay engine produces periodic returns, usually every 21 trading days.
    The regime table is daily. This function assigns the most recent available
    regime to each strategy return date.
    """
    if strategy_returns.empty:
        return pd.Series(dtype="object")

    regime = regime.dropna().sort_index()
    aligned_regime = []

    for date in strategy_returns.index:
        available = regime.loc[regime.index <= date]

        if available.empty:
            aligned_regime.append("neutral")
        else:
            aligned_regime.append(str(available.iloc[-1]))

    return pd.Series(aligned_regime, index=strategy_returns.index, name="regime")


def regime_performance_summary(
    strategy_returns: pd.DataFrame,
    regime: pd.Series,
) -> pd.DataFrame:
    """
    Summarize strategy behavior by regime.

    This table shows whether a strategy behaves differently in calm, fragile,
    stress, and extreme-stress environments.
    """
    aligned_regime = align_regime_to_strategy_dates(strategy_returns, regime)

    combined = strategy_returns.copy()
    combined["regime"] = aligned_regime

    rows = []

    for regime_name, regime_data in combined.groupby("regime"):
        strategy_columns = [col for col in regime_data.columns if col != "regime"]

        for strategy in strategy_columns:
            series = regime_data[strategy].dropna()

            if series.empty:
                continue

            rows.append(
                {
                    "regime": regime_name,
                    "strategy": strategy,
                    "average_period_return": series.mean(),
                    "median_period_return": series.median(),
                    "best_period": series.max(),
                    "worst_period": series.min(),
                    "positive_hit_rate": (series > 0).mean(),
                    "observations": len(series),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "regime",
                "strategy",
                "average_period_return",
                "median_period_return",
                "best_period",
                "worst_period",
                "positive_hit_rate",
                "observations",
            ]
        )

    return pd.DataFrame(rows)


def stress_window_summary(
    strategy_returns: pd.DataFrame,
    regime: pd.Series,
    stress_regimes: tuple[str, ...] = ("stress", "extreme_stress"),
    benchmark_column: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Evaluate strategy behavior only during stress regimes.

    This is the key table for portfolio review because it asks whether overlays
    help when passive exposure is under pressure.
    """
    aligned_regime = align_regime_to_strategy_dates(strategy_returns, regime)

    combined = strategy_returns.copy()
    combined["regime"] = aligned_regime

    stress_data = combined[combined["regime"].isin(stress_regimes)].dropna()

    rows = []

    if stress_data.empty:
        return pd.DataFrame(
            columns=[
                "strategy",
                "average_stress_return",
                "median_stress_return",
                "worst_stress_return",
                "best_stress_return",
                "hit_rate_vs_passive_in_stress",
                "downside_protection_rate",
                "observations",
            ]
        )

    benchmark = stress_data[benchmark_column]

    for strategy in [col for col in stress_data.columns if col != "regime"]:
        series = stress_data[strategy].dropna()

        if series.empty:
            continue

        hit_rate_vs_passive = np.nan
        downside_protection_rate = np.nan

        if strategy != benchmark_column:
            aligned = pd.concat(
                {
                    "strategy": series,
                    "benchmark": benchmark,
                },
                axis=1,
            ).dropna()

            if not aligned.empty:
                hit_rate_vs_passive = (
                    aligned["strategy"] > aligned["benchmark"]
                ).mean()

                benchmark_negative = aligned[aligned["benchmark"] < 0]

                if not benchmark_negative.empty:
                    downside_protection_rate = (
                        benchmark_negative["strategy"]
                        > benchmark_negative["benchmark"]
                    ).mean()

        rows.append(
            {
                "strategy": strategy,
                "average_stress_return": series.mean(),
                "median_stress_return": series.median(),
                "worst_stress_return": series.min(),
                "best_stress_return": series.max(),
                "hit_rate_vs_passive_in_stress": hit_rate_vs_passive,
                "downside_protection_rate": downside_protection_rate,
                "observations": len(series),
            }
        )

    return pd.DataFrame(rows).set_index("strategy")


def stress_window_interpretation(stress_summary: pd.DataFrame) -> str:
    """
    Produce a compact interpretation of the stress-window table.
    """
    if stress_summary.empty:
        return (
            "No stress-window observations were available under the current regime "
            "definition. The model needs either a longer sample or a broader stress "
            "definition before drawing stress-period conclusions."
        )

    valid_worst = stress_summary["worst_stress_return"].dropna()
    valid_avg = stress_summary["average_stress_return"].dropna()

    if valid_worst.empty or valid_avg.empty:
        return (
            "Stress-window diagnostics were generated, but the available observations "
            "are not enough to rank strategy behavior with confidence."
        )

    best_worst = str(valid_worst.idxmax())
    best_average = str(valid_avg.idxmax())

    return (
        f"Stress-window read: `{best_worst}` showed the strongest worst-period "
        f"protection during stress windows, while `{best_average}` showed the "
        "strongest average stress-period return. The portfolio question is whether "
        "the protection benefit is large enough to justify the active risk and "
        "implementation complexity."
    )
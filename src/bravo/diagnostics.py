"""
Regime, stress-window, and strategy help-hurt diagnostics for BRAVO Lab.

This module evaluates whether overlay strategies work when they matter most:
during fragile, stress, and extreme-stress market regimes.

It also explains when each overlay helps or hurts relative to passive Brazilian
equity exposure. The purpose is to move beyond full-sample performance and test
the decision logic under market pressure.
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


def strategy_help_hurt_diagnostics(
    strategy_returns: pd.DataFrame,
    benchmark_column: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Diagnose when each overlay helps or hurts versus passive exposure.

    This table separates active performance into:
    - periods when passive exposure is positive
    - periods when passive exposure is negative
    - periods when the overlay beats passive
    - periods when the overlay lags passive

    The goal is to explain the trade-off, not only rank strategies.
    """
    if benchmark_column not in strategy_returns.columns:
        raise KeyError(f"Benchmark column not found: {benchmark_column}")

    benchmark = strategy_returns[benchmark_column].dropna()
    rows = []

    for strategy in strategy_returns.columns:
        if strategy == benchmark_column:
            continue

        aligned = pd.concat(
            {
                "strategy": strategy_returns[strategy],
                "benchmark": benchmark,
            },
            axis=1,
        ).dropna()

        if aligned.empty:
            rows.append(
                {
                    "strategy": strategy,
                    "avg_active_return": np.nan,
                    "avg_active_when_passive_positive": np.nan,
                    "avg_active_when_passive_negative": np.nan,
                    "hit_rate_vs_passive": np.nan,
                    "missed_upside_rate": np.nan,
                    "downside_protection_rate": np.nan,
                    "best_active_period": np.nan,
                    "worst_active_period": np.nan,
                    "primary_help_zone": "insufficient_data",
                    "primary_hurt_zone": "insufficient_data",
                    "observations": 0,
                }
            )
            continue

        active = aligned["strategy"] - aligned["benchmark"]
        passive_positive = aligned[aligned["benchmark"] > 0]
        passive_negative = aligned[aligned["benchmark"] < 0]

        avg_active_positive = np.nan
        missed_upside_rate = np.nan

        if not passive_positive.empty:
            active_positive = passive_positive["strategy"] - passive_positive["benchmark"]
            avg_active_positive = active_positive.mean()
            missed_upside_rate = (
                passive_positive["strategy"] < passive_positive["benchmark"]
            ).mean()

        avg_active_negative = np.nan
        downside_protection_rate = np.nan

        if not passive_negative.empty:
            active_negative = passive_negative["strategy"] - passive_negative["benchmark"]
            avg_active_negative = active_negative.mean()
            downside_protection_rate = (
                passive_negative["strategy"] > passive_negative["benchmark"]
            ).mean()

        hit_rate = (aligned["strategy"] > aligned["benchmark"]).mean()

        primary_help_zone = "mixed"
        if not np.isnan(avg_active_negative) and avg_active_negative > 0:
            primary_help_zone = "downside_protection"
        elif not np.isnan(avg_active_positive) and avg_active_positive > 0:
            primary_help_zone = "upside_participation"
        elif active.mean() > 0:
            primary_help_zone = "broad_active_return"

        primary_hurt_zone = "mixed"
        if not np.isnan(avg_active_positive) and avg_active_positive < 0:
            primary_hurt_zone = "missed_upside"
        elif not np.isnan(avg_active_negative) and avg_active_negative < 0:
            primary_hurt_zone = "failed_protection"
        elif active.mean() < 0:
            primary_hurt_zone = "negative_active_return"

        rows.append(
            {
                "strategy": strategy,
                "avg_active_return": active.mean(),
                "avg_active_when_passive_positive": avg_active_positive,
                "avg_active_when_passive_negative": avg_active_negative,
                "hit_rate_vs_passive": hit_rate,
                "missed_upside_rate": missed_upside_rate,
                "downside_protection_rate": downside_protection_rate,
                "best_active_period": active.max(),
                "worst_active_period": active.min(),
                "primary_help_zone": primary_help_zone,
                "primary_hurt_zone": primary_hurt_zone,
                "observations": len(aligned),
            }
        )

    return pd.DataFrame(rows).set_index("strategy")


def strategy_help_hurt_interpretation(help_hurt: pd.DataFrame) -> str:
    """
    Produce a compact interpretation of the help-hurt diagnostics.
    """
    if help_hurt.empty:
        return (
            "No help-hurt diagnostics were available. The strategy table needs "
            "valid overlay and passive return series before interpretation."
        )

    valid_downside = help_hurt["downside_protection_rate"].dropna()
    valid_upside_drag = help_hurt["missed_upside_rate"].dropna()

    if valid_downside.empty:
        best_downside = "NA"
    else:
        best_downside = str(valid_downside.idxmax())

    if valid_upside_drag.empty:
        highest_upside_drag = "NA"
    else:
        highest_upside_drag = str(valid_upside_drag.idxmax())

    return (
        f"Help-hurt read: `{best_downside}` currently shows the strongest downside "
        "protection behavior versus passive exposure. "
        f"`{highest_upside_drag}` shows the highest missed-upside risk when passive "
        "Brazilian equity is positive. This is the central overlay trade-off: the "
        "portfolio can reduce left-tail pain, but protection and income strategies "
        "can also give away part of the rebound."
    )
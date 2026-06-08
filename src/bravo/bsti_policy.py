"""
BSTI overlay policy layer for BRAVO Lab.

This module converts the Brazil Stress Transmission Index into a simple,
inspectable overlay policy.

The goal is portfolio governance, not prediction:

- low BSTI: stay passive
- medium BSTI: collect income through covered calls
- high BSTI: use collar protection

The policy can be compared against passive exposure, covered calls, collars, and
the original local-regime stress-aware overlay.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def bsti_policy_signal(
    bsti_score: float,
    warning_threshold: float = 15.0,
    stress_threshold: float = 33.0,
) -> str:
    """
    Convert a BSTI score into an overlay policy signal.
    """
    if pd.isna(bsti_score):
        return "passive_brazil_equity"

    if bsti_score >= stress_threshold:
        return "collar"

    if bsti_score >= warning_threshold:
        return "covered_call"

    return "passive_brazil_equity"


def _latest_bsti_at_or_before(
    bsti_table: pd.DataFrame,
    date: pd.Timestamp,
) -> pd.Series:
    """
    Get the latest BSTI row available at or before a strategy date.
    """
    if bsti_table.empty:
        return pd.Series(dtype="object")

    clean = bsti_table.dropna(subset=["bsti_0_100"]).sort_index()
    available = clean.loc[clean.index <= date]

    if available.empty:
        return pd.Series(dtype="object")

    return available.iloc[-1]


def build_bsti_policy_overlay_returns(
    strategy_returns: pd.DataFrame,
    bsti_table: pd.DataFrame,
    warning_threshold: float = 15.0,
    stress_threshold: float = 33.0,
    benchmark_column: str = "passive_brazil_equity",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build a BSTI-driven overlay return series.

    The function selects one existing strategy return at each rebalance date:
    passive exposure, covered call, or collar.
    """
    required_columns = [
        "passive_brazil_equity",
        "covered_call",
        "collar",
    ]

    missing_columns = [col for col in required_columns if col not in strategy_returns.columns]

    if missing_columns:
        raise KeyError(f"Missing strategy return columns: {missing_columns}")

    policy_returns = []
    decisions = []

    for date, row in strategy_returns.iterrows():
        bsti_row = _latest_bsti_at_or_before(bsti_table, date)

        if bsti_row.empty:
            bsti_score = np.nan
            bsti_regime = "neutral"
            dominant_channel = "unknown"
        else:
            bsti_score = float(bsti_row.get("bsti_0_100", np.nan))
            bsti_regime = str(bsti_row.get("bsti_regime", "neutral"))
            dominant_channel = str(bsti_row.get("dominant_pressure_channel", "unknown"))

        selected_strategy = bsti_policy_signal(
            bsti_score=bsti_score,
            warning_threshold=warning_threshold,
            stress_threshold=stress_threshold,
        )

        selected_return = row[selected_strategy]

        benchmark_return = row[benchmark_column]

        policy_returns.append(selected_return)

        decisions.append(
            {
                "date": date,
                "bsti_0_100": bsti_score,
                "bsti_regime": bsti_regime,
                "dominant_pressure_channel": dominant_channel,
                "selected_strategy": selected_strategy,
                "selected_return": selected_return,
                "benchmark_return": benchmark_return,
                "active_return": selected_return - benchmark_return,
                "warning_threshold": warning_threshold,
                "stress_threshold": stress_threshold,
            }
        )

    output_returns = strategy_returns.copy()
    output_returns["bsti_policy_overlay"] = pd.Series(
        policy_returns,
        index=strategy_returns.index,
        name="bsti_policy_overlay",
    )

    decision_table = pd.DataFrame(decisions).set_index("date")

    return output_returns, decision_table


def bsti_policy_selection_summary(
    decision_table: pd.DataFrame,
) -> pd.DataFrame:
    """
    Summarize how often each policy action is selected.
    """
    if decision_table.empty:
        return pd.DataFrame()

    rows = []

    total_observations = len(decision_table)

    for selected_strategy, data in decision_table.groupby("selected_strategy"):
        rows.append(
            {
                "selected_strategy": selected_strategy,
                "observations": len(data),
                "share": len(data) / total_observations,
                "avg_bsti_0_100": data["bsti_0_100"].mean(),
                "avg_selected_return": data["selected_return"].mean(),
                "avg_benchmark_return": data["benchmark_return"].mean(),
                "avg_active_return": data["active_return"].mean(),
                "positive_active_rate": (data["active_return"] > 0).mean(),
            }
        )

    return pd.DataFrame(rows)


def _max_drawdown_from_returns(
    returns: pd.Series,
) -> float:
    """
    Calculate max drawdown from periodic returns.
    """
    clean = returns.dropna()

    if clean.empty:
        return np.nan

    cumulative = (1.0 + clean).cumprod()
    running_peak = cumulative.cummax()

    return (cumulative / running_peak - 1.0).min()


def bsti_policy_comparison_summary(
    policy_return_table: pd.DataFrame,
    benchmark_column: str = "passive_brazil_equity",
    periods_per_year: float = 12.0,
) -> pd.DataFrame:
    """
    Compare the BSTI policy overlay against available strategy return columns.
    """
    if policy_return_table.empty:
        return pd.DataFrame()

    if benchmark_column not in policy_return_table.columns:
        raise KeyError(f"Benchmark column not found: {benchmark_column}")

    benchmark = policy_return_table[benchmark_column].dropna()
    rows = []

    for strategy in policy_return_table.columns:
        series = policy_return_table[strategy].dropna()

        aligned = pd.concat(
            {
                "strategy": series,
                "benchmark": benchmark,
            },
            axis=1,
        ).dropna()

        if aligned.empty:
            continue

        active = aligned["strategy"] - aligned["benchmark"]

        annualized_return = aligned["strategy"].mean() * periods_per_year
        annualized_volatility = aligned["strategy"].std(ddof=1) * np.sqrt(periods_per_year)

        tracking_error = active.std(ddof=1) * np.sqrt(periods_per_year)
        annualized_active_return = active.mean() * periods_per_year

        information_ratio = np.nan
        if not np.isclose(tracking_error, 0.0):
            information_ratio = annualized_active_return / tracking_error

        rows.append(
            {
                "strategy": strategy,
                "annualized_return": annualized_return,
                "annualized_volatility": annualized_volatility,
                "max_drawdown": _max_drawdown_from_returns(aligned["strategy"]),
                "annualized_active_return": annualized_active_return,
                "tracking_error": tracking_error,
                "information_ratio": information_ratio,
                "hit_rate_vs_passive": (
                    aligned["strategy"] > aligned["benchmark"]
                ).mean(),
                "avg_period_return": aligned["strategy"].mean(),
                "avg_active_return": active.mean(),
                "best_active_period": active.max(),
                "worst_active_period": active.min(),
                "observations": len(aligned),
            }
        )

    return pd.DataFrame(rows).set_index("strategy")


def bsti_policy_interpretation(
    policy_comparison: pd.DataFrame,
    selection_summary: pd.DataFrame,
) -> str:
    """
    Produce a compact interpretation of the BSTI policy layer.
    """
    if policy_comparison.empty:
        return (
            "No BSTI policy comparison was available. The policy layer needs valid "
            "strategy returns and BSTI values before interpretation."
        )

    if "bsti_policy_overlay" in policy_comparison.index:
        policy_row = policy_comparison.loc["bsti_policy_overlay"]
        policy_ir = policy_row.get("information_ratio", np.nan)
        policy_te = policy_row.get("tracking_error", np.nan)
        policy_active = policy_row.get("annualized_active_return", np.nan)
    else:
        policy_ir = np.nan
        policy_te = np.nan
        policy_active = np.nan

    if selection_summary.empty:
        dominant_action = "NA"
    else:
        dominant = selection_summary.sort_values("share", ascending=False).iloc[0]
        dominant_action = str(dominant["selected_strategy"])

    return (
        f"BSTI policy read: the BSTI-driven policy most often selected "
        f"`{dominant_action}`. Its annualized active return is "
        f"`{policy_active:.2%}` with tracking error `{policy_te:.2%}` and "
        f"information ratio `{policy_ir:.2f}`. This turns BSTI from a dashboard "
        "into a governable overlay-selection rule that can be compared against "
        "passive exposure, covered calls, collars, and the local-regime stress-aware "
        "overlay."
    )


"""
Institutional report generation for BRAVO Lab.

This module turns the BRAVO Lab baseline pipeline into a decision memo:
market state, data provenance, regime diagnosis, overlay trade-off, active risk,
results SWOT, decision bias, model limits, and next risk signals.

The report is written for portfolio review. It is not a trading recommendation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from bravo.bsti_calibration import (
    best_bsti_calibration_by_horizon,
    bsti_calibration_interpretation,
    build_bsti_calibration_grid,
)
from bravo.bsti_policy import (
    bsti_policy_comparison_summary,
    bsti_policy_interpretation,
    bsti_policy_selection_summary,
    build_bsti_policy_overlay_returns,
)
from bravo.bsti_transitions import (
    bsti_transition_interpretation,
    build_bsti_escalation_summary,
    build_bsti_pressure_channel_transition_summary,
    build_bsti_state_duration_summary,
    build_bsti_transition_matrix,
    prepare_bsti_state_table,
)
from bravo.bsti_validation import (
    build_bsti_forward_outcomes,
    bsti_overlay_threshold_validation,
    bsti_threshold_validation,
    bsti_validation_interpretation,
)
from bravo.premium_figures import build_report_figure_set, figure_markdown_gallery
from bravo.config import BASELINE_REPORT_PATH, PROCESSED_DATA_DIR, REPORTS_DIR, TICKERS
from bravo.data import load_market_data
from bravo.diagnostics import (
    option_attribution_by_drawdown_bucket,
    option_attribution_by_regime,
    option_attribution_context_interpretation,
    option_overlay_attribution,
    option_overlay_attribution_interpretation,
    option_overlay_attribution_summary,
    drawdown_depth_diagnostics,
    drawdown_recovery_interpretation,
    recovery_window_diagnostics,
    active_risk_by_regime,
    active_risk_by_regime_interpretation,
    implementation_drag_diagnostics,
    implementation_drag_interpretation,
    regime_performance_summary,
    strategy_help_hurt_diagnostics,
    strategy_help_hurt_interpretation,
    stress_window_interpretation,
    stress_window_summary,
)
from bravo.metrics import summarize_performance
from bravo.strategies import build_overlay_return_table
from bravo.stress_signals import (
    build_stress_signal_table,
    stress_signal_interpretation,
    stress_signal_summary,
)
from bravo.stress_index import (
    build_brazil_stress_transmission_index,
    bsti_component_summary,
    bsti_interpretation,
    bsti_regime_distribution,
)
from bravo.volatility import build_baseline_regime_table


def _format_percentage(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value:.2%}"


def _format_number(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value:.3f}"


def _performance_table_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Asset",
        "Ann. Return",
        "Ann. Volatility",
        "Sharpe",
        "Sortino",
        "Max Drawdown",
        "VaR 95%",
        "CVaR 95%",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for asset, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(asset),
                    _format_percentage(row["annualized_return"]),
                    _format_percentage(row["annualized_volatility"]),
                    _format_number(row["sharpe_ratio"]),
                    _format_number(row["sortino_ratio"]),
                    _format_percentage(row["max_drawdown"]),
                    _format_percentage(row["historical_var_95"]),
                    _format_percentage(row["historical_cvar_95"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _regime_counts_to_markdown(regime_table: pd.DataFrame) -> str:
    counts = (
        regime_table["regime"]
        .value_counts()
        .rename_axis("regime")
        .reset_index(name="observations")
    )

    lines = [
        "| Regime | Observations | Share |",
        "| --- | ---: | ---: |",
    ]

    total = counts["observations"].sum()

    for _, row in counts.iterrows():
        share = row["observations"] / total if total else 0
        lines.append(f"| {row['regime']} | {int(row['observations'])} | {share:.2%} |")

    return "\n".join(lines)


def _max_drawdown_from_period_returns(returns: pd.Series) -> float:
    series = returns.dropna()

    if series.empty:
        return np.nan

    cumulative = (1 + series).cumprod()
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1

    return float(drawdown.min())


def _summarize_periodic_strategy_returns(
    returns: pd.DataFrame,
    periods_per_year: float,
) -> pd.DataFrame:
    rows = []

    for column in returns.columns:
        series = returns[column].dropna()

        if series.empty:
            rows.append(
                {
                    "strategy": column,
                    "annualized_return": np.nan,
                    "annualized_volatility": np.nan,
                    "sharpe_ratio": np.nan,
                    "max_drawdown": np.nan,
                    "best_period": np.nan,
                    "worst_period": np.nan,
                    "observations": 0,
                }
            )
            continue

        cumulative_return = (1 + series).prod()
        years = len(series) / periods_per_year

        annualized_return = cumulative_return ** (1 / years) - 1 if years > 0 else np.nan
        annualized_volatility = series.std() * np.sqrt(periods_per_year)

        sharpe = np.nan
        if series.std() != 0 and not np.isnan(series.std()):
            sharpe = (series.mean() / series.std()) * np.sqrt(periods_per_year)

        rows.append(
            {
                "strategy": column,
                "annualized_return": annualized_return,
                "annualized_volatility": annualized_volatility,
                "sharpe_ratio": sharpe,
                "max_drawdown": _max_drawdown_from_period_returns(series),
                "best_period": series.max(),
                "worst_period": series.min(),
                "observations": len(series),
            }
        )

    return pd.DataFrame(rows).set_index("strategy")


def _overlay_table_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Strategy",
        "Ann. Return",
        "Ann. Volatility",
        "Sharpe",
        "Max Drawdown",
        "Best Period",
        "Worst Period",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for strategy, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(strategy),
                    _format_percentage(row["annualized_return"]),
                    _format_percentage(row["annualized_volatility"]),
                    _format_number(row["sharpe_ratio"]),
                    _format_percentage(row["max_drawdown"]),
                    _format_percentage(row["best_period"]),
                    _format_percentage(row["worst_period"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _active_risk_summary(
    overlay_returns: pd.DataFrame,
    periods_per_year: float,
    benchmark_column: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Calculate active risk diagnostics versus passive Brazilian equity.

    The purpose is to avoid judging overlays only by absolute return.
    A portfolio desk needs to know whether the active deviation from the
    benchmark is compensated.
    """
    if benchmark_column not in overlay_returns.columns:
        raise KeyError(f"Benchmark column not found: {benchmark_column}")

    benchmark = overlay_returns[benchmark_column].dropna()
    rows = []

    for column in overlay_returns.columns:
        if column == benchmark_column:
            continue

        aligned = pd.concat(
            {
                "strategy": overlay_returns[column],
                "benchmark": benchmark,
            },
            axis=1,
        ).dropna()

        if aligned.empty:
            rows.append(
                {
                    "strategy": column,
                    "annualized_active_return": np.nan,
                    "tracking_error": np.nan,
                    "information_ratio": np.nan,
                    "hit_rate_vs_benchmark": np.nan,
                    "downside_hit_rate": np.nan,
                    "avg_active_return": np.nan,
                    "worst_active_period": np.nan,
                    "observations": 0,
                }
            )
            continue

        active = aligned["strategy"] - aligned["benchmark"]
        active_return = active.mean() * periods_per_year
        tracking_error = active.std() * np.sqrt(periods_per_year)

        information_ratio = np.nan
        if tracking_error != 0 and not np.isnan(tracking_error):
            information_ratio = active_return / tracking_error

        hit_rate = (aligned["strategy"] > aligned["benchmark"]).mean()

        downside_periods = aligned[aligned["benchmark"] < 0]
        downside_hit_rate = np.nan
        if not downside_periods.empty:
            downside_hit_rate = (
                downside_periods["strategy"] > downside_periods["benchmark"]
            ).mean()

        rows.append(
            {
                "strategy": column,
                "annualized_active_return": active_return,
                "tracking_error": tracking_error,
                "information_ratio": information_ratio,
                "hit_rate_vs_benchmark": hit_rate,
                "downside_hit_rate": downside_hit_rate,
                "avg_active_return": active.mean(),
                "worst_active_period": active.min(),
                "observations": len(aligned),
            }
        )

    return pd.DataFrame(rows).set_index("strategy")


def _active_risk_to_markdown(active_summary: pd.DataFrame) -> str:
    headers = [
        "Strategy",
        "Ann. Active Return",
        "Tracking Error",
        "Information Ratio",
        "Hit Rate",
        "Downside Hit Rate",
        "Worst Active Period",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for strategy, row in active_summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(strategy),
                    _format_percentage(row["annualized_active_return"]),
                    _format_percentage(row["tracking_error"]),
                    _format_number(row["information_ratio"]),
                    _format_percentage(row["hit_rate_vs_benchmark"]),
                    _format_percentage(row["downside_hit_rate"]),
                    _format_percentage(row["worst_active_period"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)



def _regime_performance_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Regime",
        "Strategy",
        "Avg. Period Return",
        "Median Period Return",
        "Best Period",
        "Worst Period",
        "Positive Hit Rate",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["regime"]),
                    str(row["strategy"]),
                    _format_percentage(row["average_period_return"]),
                    _format_percentage(row["median_period_return"]),
                    _format_percentage(row["best_period"]),
                    _format_percentage(row["worst_period"]),
                    _format_percentage(row["positive_hit_rate"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _stress_window_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Strategy",
        "Avg. Stress Return",
        "Median Stress Return",
        "Worst Stress Return",
        "Best Stress Return",
        "Hit Rate vs Passive",
        "Downside Protection Rate",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for strategy, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(strategy),
                    _format_percentage(row["average_stress_return"]),
                    _format_percentage(row["median_stress_return"]),
                    _format_percentage(row["worst_stress_return"]),
                    _format_percentage(row["best_stress_return"]),
                    _format_percentage(row["hit_rate_vs_passive_in_stress"]),
                    _format_percentage(row["downside_protection_rate"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)



def _help_hurt_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Strategy",
        "Avg. Active Return",
        "Active When Passive Up",
        "Active When Passive Down",
        "Hit Rate",
        "Missed Upside Rate",
        "Downside Protection Rate",
        "Best Active Period",
        "Worst Active Period",
        "Primary Help",
        "Primary Hurt",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for strategy, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(strategy),
                    _format_percentage(row["avg_active_return"]),
                    _format_percentage(row["avg_active_when_passive_positive"]),
                    _format_percentage(row["avg_active_when_passive_negative"]),
                    _format_percentage(row["hit_rate_vs_passive"]),
                    _format_percentage(row["missed_upside_rate"]),
                    _format_percentage(row["downside_protection_rate"]),
                    _format_percentage(row["best_active_period"]),
                    _format_percentage(row["worst_active_period"]),
                    str(row["primary_help_zone"]),
                    str(row["primary_hurt_zone"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)



def _implementation_drag_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Strategy",
        "Gross Active",
        "Implementation Drag",
        "Net Active",
        "Total Drag",
        "Drag / Gross Signal",
        "Cost Survival",
        "Active When Passive Up",
        "Active When Passive Down",
        "Best Net Active",
        "Worst Net Active",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for strategy, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(strategy),
                    _format_percentage(row["avg_gross_active_return"]),
                    _format_percentage(row["avg_implementation_drag"]),
                    _format_percentage(row["avg_net_active_return"]),
                    _format_percentage(row["total_implementation_drag"]),
                    _format_number(row["drag_to_gross_signal"]),
                    _format_number(row["cost_survival_ratio"]),
                    _format_percentage(row["avg_active_when_passive_positive"]),
                    _format_percentage(row["avg_active_when_passive_negative"]),
                    _format_percentage(row["best_net_active_period"]),
                    _format_percentage(row["worst_net_active_period"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)



def _active_risk_by_regime_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Regime",
        "Strategy",
        "Annualized Active Return",
        "Tracking Error",
        "Information Ratio",
        "Hit Rate",
        "Downside Hit Rate",
        "Avg. Active Period",
        "Best Active Period",
        "Worst Active Period",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["regime"]),
                    str(row["strategy"]),
                    _format_percentage(row["annualized_active_return"]),
                    _format_percentage(row["tracking_error"]),
                    _format_number(row["information_ratio"]),
                    _format_percentage(row["hit_rate_vs_passive"]),
                    _format_percentage(row["downside_hit_rate"]),
                    _format_percentage(row["avg_period_active_return"]),
                    _format_percentage(row["best_active_period"]),
                    _format_percentage(row["worst_active_period"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)



def _drawdown_depth_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Drawdown Bucket",
        "Strategy",
        "Avg. Strategy Return",
        "Avg. Benchmark Return",
        "Avg. Active Return",
        "Hit Rate",
        "Downside Protection Rate",
        "Best Active Period",
        "Worst Active Period",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["drawdown_bucket"]),
                    str(row["strategy"]),
                    _format_percentage(row["avg_strategy_return"]),
                    _format_percentage(row["avg_benchmark_return"]),
                    _format_percentage(row["avg_active_return"]),
                    _format_percentage(row["hit_rate_vs_passive"]),
                    _format_percentage(row["downside_protection_rate"]),
                    _format_percentage(row["best_active_period"]),
                    _format_percentage(row["worst_active_period"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _recovery_window_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Strategy",
        "Avg. Strategy Return",
        "Avg. Benchmark Return",
        "Avg. Active in Recovery",
        "Hit Rate in Recovery",
        "Missed Recovery Rate",
        "Best Active Recovery",
        "Worst Active Recovery",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for strategy, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(strategy),
                    _format_percentage(row["avg_strategy_return"]),
                    _format_percentage(row["avg_benchmark_return"]),
                    _format_percentage(row["avg_active_return_in_recovery"]),
                    _format_percentage(row["hit_rate_vs_passive_in_recovery"]),
                    _format_percentage(row["missed_recovery_rate"]),
                    _format_percentage(row["best_active_recovery_period"]),
                    _format_percentage(row["worst_active_recovery_period"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)



def _option_attribution_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Strategy",
        "Avg. Underlying Return",
        "Avg. Call Premium Income",
        "Avg. Put Protection Cost",
        "Avg. Option Payoff Effect",
        "Avg. Implementation Drag",
        "Avg. Gross Overlay Effect",
        "Avg. Net Overlay Effect",
        "Avg. Net Strategy Return",
        "Positive Net Overlay Rate",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for strategy, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(strategy),
                    _format_percentage(row["avg_underlying_return"]),
                    _format_percentage(row["avg_call_premium_income"]),
                    _format_percentage(row["avg_put_protection_cost"]),
                    _format_percentage(row["avg_option_payoff_effect"]),
                    _format_percentage(row["avg_implementation_drag"]),
                    _format_percentage(row["avg_gross_overlay_effect"]),
                    _format_percentage(row["avg_net_overlay_effect"]),
                    _format_percentage(row["avg_net_strategy_return"]),
                    _format_percentage(row["positive_net_overlay_rate"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)



def _option_attribution_context_to_markdown(
    summary: pd.DataFrame,
    context_column: str,
) -> str:
    headers = [
        "Context",
        "Strategy",
        "Avg. Underlying Return",
        "Avg. Call Premium Income",
        "Avg. Put Protection Cost",
        "Avg. Option Payoff Effect",
        "Avg. Implementation Drag",
        "Avg. Net Overlay Effect",
        "Positive Net Overlay Rate",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row[context_column]),
                    str(row["strategy"]),
                    _format_percentage(row["avg_underlying_return"]),
                    _format_percentage(row["avg_call_premium_income"]),
                    _format_percentage(row["avg_put_protection_cost"]),
                    _format_percentage(row["avg_option_payoff_effect"]),
                    _format_percentage(row["avg_implementation_drag"]),
                    _format_percentage(row["avg_net_overlay_effect"]),
                    _format_percentage(row["positive_net_overlay_rate"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)



def _stress_signal_summary_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Date",
        "Composite Stress Score",
        "Stress Regime",
        "Top Pressure 1",
        "Value 1",
        "Top Pressure 2",
        "Value 2",
        "Top Pressure 3",
        "Value 3",
        "Brazil Drawdown",
        "Brazil 21D Vol",
        "VIX Level",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(pd.to_datetime(row["date"]).date()),
                    _format_number(row["multi_asset_stress_score"]),
                    str(row["multi_asset_stress_regime"]),
                    str(row["top_pressure_1"]),
                    _format_number(row["top_pressure_1_value"]),
                    str(row["top_pressure_2"]),
                    _format_number(row["top_pressure_2_value"]),
                    str(row["top_pressure_3"]),
                    _format_number(row["top_pressure_3_value"]),
                    _format_percentage(row["brazil_drawdown"]),
                    _format_percentage(row["brazil_realized_vol_21d"]),
                    _format_number(row["vix_level"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)



def _bsti_summary_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Date",
        "BSTI 0-100",
        "Raw Score",
        "Regime",
        "Stress Breadth",
        "Active Channels",
        "Dominant Channel",
        "Dominant Value",
        "Top Channel 1",
        "Value 1",
        "Top Channel 2",
        "Value 2",
        "Top Channel 3",
        "Value 3",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(pd.to_datetime(row["date"]).date()),
                    _format_number(row["bsti_0_100"]),
                    _format_number(row["bsti_raw_score"]),
                    str(row["bsti_regime"]),
                    _format_number(row["stress_breadth"]),
                    str(int(row["active_pressure_channels"])),
                    str(row["dominant_pressure_channel"]),
                    _format_number(row["dominant_pressure_value"]),
                    str(row["top_channel_1"]),
                    _format_number(row["top_channel_1_value"]),
                    str(row["top_channel_2"]),
                    _format_number(row["top_channel_2_value"]),
                    str(row["top_channel_3"]),
                    _format_number(row["top_channel_3_value"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _bsti_regime_distribution_to_markdown(summary: pd.DataFrame) -> str:
    headers = ["BSTI Regime", "Observations", "Share"]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["bsti_regime"]),
                    str(int(row["observations"])),
                    _format_percentage(row["share"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)



def _bsti_threshold_validation_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Horizon",
        "BSTI Threshold",
        "Obs.",
        "Signal Obs.",
        "Signal Freq.",
        "Avg Return Signal On",
        "Avg Return Signal Off",
        "Avg Max DD Signal On",
        "Avg Max DD Signal Off",
        "Neg Return Precision",
        "5% DD Precision",
        "10% DD Precision",
        "5% DD Recall",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(int(row["horizon_days"])),
                    _format_number(row["bsti_threshold"]),
                    str(int(row["observations"])),
                    str(int(row["signal_observations"])),
                    _format_percentage(row["signal_frequency"]),
                    _format_percentage(row["avg_forward_return_signal_on"]),
                    _format_percentage(row["avg_forward_return_signal_off"]),
                    _format_percentage(row["avg_forward_max_drawdown_signal_on"]),
                    _format_percentage(row["avg_forward_max_drawdown_signal_off"]),
                    _format_percentage(row["future_negative_return_precision"]),
                    _format_percentage(row["future_drawdown_5pct_precision"]),
                    _format_percentage(row["future_drawdown_10pct_precision"]),
                    _format_percentage(row["future_drawdown_5pct_recall"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _bsti_overlay_validation_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "BSTI Threshold",
        "Strategy",
        "Obs.",
        "Avg Active Return",
        "Annualized Active Return",
        "Tracking Error",
        "Information Ratio",
        "Hit Rate",
        "Best Active Period",
        "Worst Active Period",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    _format_number(row["bsti_threshold"]),
                    str(row["strategy"]),
                    str(int(row["observations"])),
                    _format_percentage(row["avg_active_return"]),
                    _format_percentage(row["annualized_active_return"]),
                    _format_percentage(row["tracking_error"]),
                    _format_number(row["information_ratio"]),
                    _format_percentage(row["hit_rate_vs_passive"]),
                    _format_percentage(row["best_active_period"]),
                    _format_percentage(row["worst_active_period"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)





def _bsti_transition_matrix_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "From State",
        "To State",
        "Transitions",
        "Probability",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["from_state"]),
                    str(row["to_state"]),
                    str(int(row["transitions"])),
                    _format_percentage(row["probability"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _bsti_state_duration_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "State",
        "Episodes",
        "Avg Duration",
        "Median Duration",
        "Max Duration",
        "Avg BSTI",
        "Max BSTI",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["state"]),
                    str(int(row["episodes"])),
                    _format_number(row["avg_duration_observations"]),
                    _format_number(row["median_duration_observations"]),
                    _format_number(row["max_duration_observations"]),
                    _format_number(row["avg_bsti_0_100"]),
                    _format_number(row["max_bsti_0_100"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _bsti_escalation_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Warning Events",
        "Lookahead Obs.",
        "Escalation Rate",
        "Stay Warning/Stress Rate",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(int(row["warning_events"])),
                    str(int(row["lookahead_observations"])),
                    _format_percentage(row["escalation_rate"]),
                    _format_percentage(row["stay_warning_or_stress_rate"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _bsti_channel_transitions_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "From Channel",
        "To Channel",
        "Transitions",
        "Probability",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    display = summary.head(12)

    for _, row in display.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["from_channel"]),
                    str(row["to_channel"]),
                    str(int(row["transitions"])),
                    _format_percentage(row["probability"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _bsti_policy_selection_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Selected Strategy",
        "Obs.",
        "Share",
        "Avg BSTI",
        "Avg Selected Return",
        "Avg Passive Return",
        "Avg Active Return",
        "Positive Active Rate",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["selected_strategy"]),
                    str(int(row["observations"])),
                    _format_percentage(row["share"]),
                    _format_number(row["avg_bsti_0_100"]),
                    _format_percentage(row["avg_selected_return"]),
                    _format_percentage(row["avg_benchmark_return"]),
                    _format_percentage(row["avg_active_return"]),
                    _format_percentage(row["positive_active_rate"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _bsti_policy_comparison_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Strategy",
        "Ann. Return",
        "Ann. Vol.",
        "Max DD",
        "Ann. Active",
        "Tracking Error",
        "Info. Ratio",
        "Hit Rate",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    display = summary.reset_index()

    for _, row in display.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["strategy"]),
                    _format_percentage(row["annualized_return"]),
                    _format_percentage(row["annualized_volatility"]),
                    _format_percentage(row["max_drawdown"]),
                    _format_percentage(row["annualized_active_return"]),
                    _format_percentage(row["tracking_error"]),
                    _format_number(row["information_ratio"]),
                    _format_percentage(row["hit_rate_vs_passive"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _bsti_calibration_grid_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Weight Scheme",
        "Horizon",
        "Threshold",
        "Governance Score",
        "Signal Freq.",
        "5% DD Precision",
        "5% DD Recall",
        "Avg Max DD Signal On",
        "Avg Max DD Signal Off",
        "Obs.",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    display = summary.sort_values(
        ["horizon_days", "governance_score"],
        ascending=[True, False],
    ).head(12)

    for _, row in display.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["weight_scheme"]),
                    str(int(row["horizon_days"])),
                    _format_number(row["bsti_threshold"]),
                    _format_number(row["governance_score"]),
                    _format_percentage(row["signal_frequency"]),
                    _format_percentage(row["future_drawdown_5pct_precision"]),
                    _format_percentage(row["future_drawdown_5pct_recall"]),
                    _format_percentage(row["avg_forward_max_drawdown_signal_on"]),
                    _format_percentage(row["avg_forward_max_drawdown_signal_off"]),
                    str(int(row["observations"])),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _bsti_best_calibration_to_markdown(summary: pd.DataFrame) -> str:
    headers = [
        "Horizon",
        "Weight Scheme",
        "Threshold",
        "Governance Score",
        "Signal Freq.",
        "5% DD Precision",
        "5% DD Recall",
        "Selection Rule",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in summary.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(int(row["horizon_days"])),
                    str(row["weight_scheme"]),
                    _format_number(row["bsti_threshold"]),
                    _format_number(row["governance_score"]),
                    _format_percentage(row["signal_frequency"]),
                    _format_percentage(row["future_drawdown_5pct_precision"]),
                    _format_percentage(row["future_drawdown_5pct_recall"]),
                    str(row["selection_rule"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _data_provenance_table(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for label, ticker in TICKERS.items():
        if label not in prices.columns:
            continue

        price_series = prices[label].dropna()

        if label in returns.columns:
            return_series = returns[label].dropna()
        else:
            return_series = pd.Series(dtype=float)

        rows.append(
            {
                "layer": "market_data",
                "item": label,
                "ticker_or_input": ticker,
                "source": "Yahoo Finance through yfinance",
                "evidence_type": "real_public_market_price_series",
                "transformation": "adjusted close prices and daily returns",
                "start_date": price_series.index.min().date()
                if not price_series.empty
                else "NA",
                "end_date": price_series.index.max().date()
                if not price_series.empty
                else "NA",
                "price_observations": len(price_series),
                "return_observations": len(return_series),
                "status": "real market proxy",
            }
        )

    rows.extend(
        [
            {
                "layer": "derived_metric",
                "item": "realized_volatility",
                "ticker_or_input": "brazil_equity returns",
                "source": "BRAVO Lab calculation",
                "evidence_type": "model_derived",
                "transformation": "rolling standard deviation annualized",
                "start_date": "derived from available market window",
                "end_date": "derived from available market window",
                "price_observations": "NA",
                "return_observations": "NA",
                "status": "derived from real market data",
            },
            {
                "layer": "derived_metric",
                "item": "drawdown",
                "ticker_or_input": "brazil_equity returns",
                "source": "BRAVO Lab calculation",
                "evidence_type": "model_derived",
                "transformation": "cumulative return versus running maximum",
                "start_date": "derived from available market window",
                "end_date": "derived from available market window",
                "price_observations": "NA",
                "return_observations": "NA",
                "status": "derived from real market data",
            },
            {
                "layer": "regime_signal",
                "item": "baseline_regime_classifier",
                "ticker_or_input": "volatility percentile and drawdown",
                "source": "BRAVO Lab rule-based classifier",
                "evidence_type": "model_generated_signal",
                "transformation": "calm, fragile, stress, extreme_stress classification",
                "start_date": "derived from available market window",
                "end_date": "derived from available market window",
                "price_observations": "NA",
                "return_observations": "NA",
                "status": "decision signal, not observed market data",
            },
            {
                "layer": "synthetic_derivatives",
                "item": "covered_call_overlay",
                "ticker_or_input": "BOVA11 proxy plus Black-Scholes premium",
                "source": "BRAVO Lab synthetic option engine",
                "evidence_type": "synthetic_research_assumption",
                "transformation": "monthly synthetic short call overlay",
                "start_date": "derived from available market window",
                "end_date": "derived from available market window",
                "price_observations": "NA",
                "return_observations": "NA",
                "status": "not real B3 option-chain evidence",
            },
            {
                "layer": "synthetic_derivatives",
                "item": "collar_overlay",
                "ticker_or_input": "BOVA11 proxy plus Black-Scholes premium",
                "source": "BRAVO Lab synthetic option engine",
                "evidence_type": "synthetic_research_assumption",
                "transformation": "monthly synthetic long put and short call overlay",
                "start_date": "derived from available market window",
                "end_date": "derived from available market window",
                "price_observations": "NA",
                "return_observations": "NA",
                "status": "not real B3 option-chain evidence",
            },
            {
                "layer": "strategy_logic",
                "item": "stress_aware_overlay",
                "ticker_or_input": "baseline regime classifier",
                "source": "BRAVO Lab switching rule",
                "evidence_type": "model_generated_strategy_rule",
                "transformation": "passive in calm, covered call in fragile, collar in stress",
                "start_date": "derived from available market window",
                "end_date": "derived from available market window",
                "price_observations": "NA",
                "return_observations": "NA",
                "status": "research rule requiring validation",
            },
        ]
    )

    return pd.DataFrame(rows)


def _data_provenance_to_markdown(provenance: pd.DataFrame) -> str:
    headers = [
        "Layer",
        "Item",
        "Source",
        "Evidence Type",
        "Status",
    ]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in provenance.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["layer"]),
                    str(row["item"]),
                    str(row["source"]),
                    str(row["evidence_type"]),
                    str(row["status"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _safe_idxmax(summary: pd.DataFrame, column: str) -> str:
    valid = summary[column].dropna()

    if valid.empty:
        return "NA"

    return str(valid.idxmax())


def _safe_idxmin(summary: pd.DataFrame, column: str) -> str:
    valid = summary[column].dropna()

    if valid.empty:
        return "NA"

    return str(valid.idxmin())


def _decision_bias(
    latest_regime: str,
    latest_drawdown: float,
    overlay_summary: pd.DataFrame,
) -> str:
    best_drawdown = _safe_idxmax(overlay_summary, "max_drawdown")
    best_sharpe = _safe_idxmax(overlay_summary, "sharpe_ratio")

    if latest_regime in {"stress", "extreme_stress"} or latest_drawdown <= -0.10:
        return (
            "Protection bias. The current signal gives more weight to drawdown control "
            "than to full upside capture. The strongest drawdown profile is currently "
            f"`{best_drawdown}`. The strongest risk-adjusted profile is currently "
            f"`{best_sharpe}`."
        )

    if latest_regime == "fragile":
        return (
            "Balanced bias. The market does not justify blind beta exposure, but it also "
            "does not force maximum protection. Income harvesting and partial protection "
            "must be compared before increasing directional exposure."
        )

    return (
        "Participation bias. The regime allows more tolerance for beta exposure. Covered "
        "call income may still add value, but the main risk is selling too much upside "
        "before a stronger recovery."
    )


def _shockbridge_signal(
    latest_regime: str,
    latest_volatility: float,
    latest_drawdown: float,
) -> str:
    if latest_regime == "extreme_stress":
        return (
            "ShockBridge Signal: capital protection dominates income extraction. "
            "Volatility should be read as a stress carrier, not only as a premium source."
        )

    if latest_regime == "stress":
        return (
            "ShockBridge Signal: the market is inside a stress transmission zone. "
            "Covered calls may monetize volatility, but collars carry stronger portfolio "
            "logic while drawdown pressure remains active."
        )

    if latest_regime == "fragile":
        return (
            "ShockBridge Signal: the market is not broken, but it is not clean. "
            "This is the zone where passive exposure can look safe before risk reprices."
        )

    return (
        "ShockBridge Signal: the market is in a participation zone. Risk control remains "
        "necessary, but the baseline evidence does not force a defensive posture."
    )


def _watch_next(latest_regime: str) -> str:
    if latest_regime in {"stress", "extreme_stress"}:
        return (
            "Watch whether drawdown stabilizes while realized volatility falls. If that "
            "does not happen, protection remains more valuable than income. If volatility "
            "falls without price repair, the market may be hiding fragility under calmer "
            "surface data."
        )

    if latest_regime == "fragile":
        return (
            "Watch the next volatility percentile shift. A move into the upper regime band "
            "should push the framework toward protection. A move lower with drawdown repair "
            "supports more participation."
        )

    return (
        "Watch whether volatility stays contained while trend holds. If volatility rises "
        "before price breaks, the warning is regime contamination. If price breaks first, "
        "drawdown becomes the primary signal."
    )


def _strategy_decision_matrix() -> str:
    return """| Strategy | Best Use | Main Risk | Portfolio Reading |
| --- | --- | --- | --- |
| Passive Brazilian Equity | Clean trend, calm regime, strong rebound | Full downside exposure | Use when upside participation matters more than protection |
| Covered Call | Fragile regime, elevated volatility, income objective | Upside is capped | Use when premium harvesting matters more than full upside capture |
| Collar | Stress regime, drawdown pressure, capital preservation | Protection cost and capped upside | Use when left-tail control matters more than return maximization |
| Stress-Aware Overlay | Regime-dependent switching | Model risk and signal timing | Uses passive in calm regimes, covered calls in fragile regimes, and collars in stress regimes |"""


def _results_swot() -> str:
    return """This SWOT does not evaluate BRAVO Lab as a business project. It evaluates the current result as a portfolio decision signal.

The purpose is simple: separate what the model already shows from what still needs proof.

| Dimension | Current Reading | Portfolio Meaning |
| --- | --- | --- |
| Strengths | The report connects market state, regime classification, risk metrics, synthetic overlay performance, and active risk diagnostics in one reproducible pipeline. | The decision maker can compare passive exposure, covered call income, collar protection, and stress-aware switching under the same data window instead of reading each strategy in isolation. |
| Weaknesses | The overlay premiums are synthetic. Real B3 option-chain behavior, liquidity, spreads, taxes, and execution costs are not yet included. | The current ranking should not be treated as live tradable evidence. It is a research signal that needs market microstructure validation. |
| Opportunities | The framework creates a path toward regime-aware overlay allocation with active-risk discipline. It can evolve from static comparison into a decision engine that changes exposure as volatility and drawdown conditions shift. | The strongest future use is not picking one permanent strategy. The value is learning when to hold beta, harvest premium, buy protection, or accept active risk. |
| Threats | The model can overstate strategy quality if synthetic option prices are too clean, if transaction costs are too low, or if full-sample performance hides stress-period failure. | The main risk is false confidence. A premium-looking result becomes dangerous if it is not tested across stress windows, costs, tracking error, and real option data. |

### SWOT Interpretation

The main strength is integration. The report does not leave the portfolio reviewer with isolated metrics. It links regime, risk, overlay behavior, and active deviation from the benchmark.

The main weakness is tradability. Synthetic option pricing is useful for building the research engine, but it is not enough for real portfolio deployment.

The main opportunity is regime switching with active-risk control. A static covered call or collar strategy is too rigid for Brazilian markets. The more valuable question is when the book should shift from participation to income to protection without taking unrewarded tracking error.

The main threat is clean-model illusion. A strategy can look strong before costs, spreads, liquidity, and stress subperiods. The next version must attack that weakness directly."""


def _report_structure() -> str:
    return """| PDF Page Target | Section | Decision Purpose |
| ---: | --- | --- |
| 1 | Executive Signal | Current regime, decision bias, and portfolio read |
| 2 | Portfolio Question | What the framework is trying to decide |
| 3 | Market State | Cross-market context for Brazil exposure |
| 4 | Data Provenance | Separates real data, derived metrics, synthetic assumptions, and model rules |
| 5 | Regime Diagnosis | Volatility, drawdown, and current regime |
| 6 | Baseline Risk Metrics | Return, risk, Sharpe, drawdown, VaR, CVaR |
| 7 | Synthetic Overlay Results | Passive versus covered call versus collar versus stress-aware overlay |
| 8 | Active Risk Diagnostics | Tracks active return, tracking error, hit rate, and information ratio |
| 9 | Active Risk by Regime | Shows where each overlay creates tracking error by market state |
| 10 | Multi-Asset Stress Signals | Adds FX, VIX, EWZ, and global-equity pressure to the stress view |
| 11 | Brazil Stress Transmission Index | Converts stress signals into a formal 0 to 100 composite index |
| 12 | BSTI Threshold Validation | Tests whether BSTI thresholds connect to future drawdowns and overlay behavior |
| 13 | BSTI Threshold Calibration | Tests alternative thresholds and component-weighting schemes |
| 14 | BSTI Overlay Policy Selection | Converts calibrated stress signals into portfolio actions |
| 15 | BSTI Signal Persistence | Tests warning-state durability, escalation, and pressure-channel transitions |
| 16 | Drawdown and Recovery Diagnostics | Tests behavior in drawdown depth and rebound windows |
| 17 | Regime and Stress Diagnostics | Tests whether the overlay helps when market pressure rises |
| 12 | Strategy Help-Hurt Diagnostics | Explains when each overlay adds value or creates drag |
| 13 | Implementation Drag Diagnostics | Separates gross signal, cost drag, and net overlay effect |
| 14 | Option Overlay Attribution | Separates premium, protection cost, payoff, drag, and net effect |
| 15 | Option Attribution by Context | Explains option components by regime and drawdown bucket |
| 16 | Overlay Decision Matrix | When each strategy is useful or dangerous |
| 17 to 18 | Results SWOT | How to cope with the signal before portfolio action |
| 13 | ShockBridge Transmission Read | How stress moves into the book |
| 14 | What To Watch Next | Confirmation signals and warning signals |
| 15 | Model Limits and Evidence Files | What is proven, what is not, and what comes next |"""


def generate_baseline_report(output_path: Path = BASELINE_REPORT_PATH) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    data = load_market_data()
    performance_summary = summarize_performance(data.returns)
    data_provenance = _data_provenance_table(
        prices=data.prices,
        returns=data.returns,
    )

    if "brazil_equity" not in data.returns.columns:
        raise KeyError("Expected 'brazil_equity' in returns. Check ticker configuration.")

    regime_table = build_baseline_regime_table(data.returns["brazil_equity"])

    stress_signal_table = build_stress_signal_table(
        prices=data.prices,
        returns=data.returns,
    )

    stress_signal_latest = stress_signal_summary(stress_signal_table)

    stress_signal_read = stress_signal_interpretation(stress_signal_latest)

    bsti_table = build_brazil_stress_transmission_index(stress_signal_table)

    bsti_latest_summary = bsti_component_summary(bsti_table)

    bsti_distribution = bsti_regime_distribution(bsti_table)

    bsti_read = bsti_interpretation(bsti_latest_summary)

    maturity_days = 21
    periods_per_year = 252 / maturity_days
    transaction_cost_bps = 5.0

    gross_overlay_returns = build_overlay_return_table(
        prices=data.prices["brazil_equity"],
        returns=data.returns["brazil_equity"],
        regime=regime_table["regime"],
        maturity_days=maturity_days,
        transaction_cost_bps=0.0,
    )

    overlay_returns = build_overlay_return_table(
        prices=data.prices["brazil_equity"],
        returns=data.returns["brazil_equity"],
        regime=regime_table["regime"],
        maturity_days=maturity_days,
        transaction_cost_bps=5.0,
    )

    overlay_summary = _summarize_periodic_strategy_returns(
        returns=overlay_returns,
        periods_per_year=periods_per_year,
    )

    active_risk_summary = _active_risk_summary(
        overlay_returns=overlay_returns,
        periods_per_year=periods_per_year,
        benchmark_column="passive_brazil_equity",
    )

    active_regime_summary = active_risk_by_regime(
        strategy_returns=overlay_returns,
        regime=regime_table["regime"],
        benchmark_column="passive_brazil_equity",
        periods_per_year=periods_per_year,
    )

    active_regime_read = active_risk_by_regime_interpretation(active_regime_summary)

    drawdown_depth_summary = drawdown_depth_diagnostics(
        strategy_returns=overlay_returns,
        benchmark_column="passive_brazil_equity",
    )

    recovery_window_summary = recovery_window_diagnostics(
        strategy_returns=overlay_returns,
        benchmark_column="passive_brazil_equity",
    )

    drawdown_recovery_read = drawdown_recovery_interpretation(
        drawdown_summary=drawdown_depth_summary,
        recovery_summary=recovery_window_summary,
    )

    bsti_forward_outcomes = build_bsti_forward_outcomes(
        bsti_table=bsti_table,
        benchmark_returns=data.returns["brazil_equity"],
        horizons=(21, 63),
    )

    bsti_threshold_validation_table = bsti_threshold_validation(
        bsti_forward_outcomes
    )

    bsti_overlay_validation_table = bsti_overlay_threshold_validation(
        bsti_table=bsti_table,
        strategy_returns=overlay_returns,
        benchmark_column="passive_brazil_equity",
        periods_per_year=periods_per_year,
    )

    bsti_validation_read = bsti_validation_interpretation(
        threshold_validation=bsti_threshold_validation_table,
        overlay_validation=bsti_overlay_validation_table,
    )

    bsti_calibration_grid = build_bsti_calibration_grid(
        stress_signal_table=stress_signal_table,
        benchmark_returns=data.returns["brazil_equity"],
        horizons=(21, 63),
    )

    bsti_best_calibration = best_bsti_calibration_by_horizon(
        bsti_calibration_grid
    )

    bsti_calibration_read = bsti_calibration_interpretation(
        bsti_best_calibration
    )

    bsti_policy_returns, bsti_policy_decisions = build_bsti_policy_overlay_returns(
        strategy_returns=overlay_returns,
        bsti_table=bsti_table,
        warning_threshold=15.0,
        stress_threshold=33.0,
    )

    bsti_policy_selection = bsti_policy_selection_summary(
        bsti_policy_decisions
    )

    bsti_policy_comparison = bsti_policy_comparison_summary(
        bsti_policy_returns
    )

    bsti_policy_read = bsti_policy_interpretation(
        policy_comparison=bsti_policy_comparison,
        selection_summary=bsti_policy_selection,
    )

    bsti_state_table = prepare_bsti_state_table(
        bsti_table=bsti_table,
        warning_threshold=15.0,
        stress_threshold=33.0,
    )

    bsti_transition_matrix = build_bsti_transition_matrix(
        bsti_state_table
    )

    bsti_state_duration_summary = build_bsti_state_duration_summary(
        bsti_state_table
    )

    bsti_escalation_summary = build_bsti_escalation_summary(
        bsti_state_table,
        lookahead_observations=3,
    )

    bsti_pressure_channel_transitions = build_bsti_pressure_channel_transition_summary(
        bsti_state_table
    )

    bsti_transition_read = bsti_transition_interpretation(
        transition_matrix=bsti_transition_matrix,
        duration_summary=bsti_state_duration_summary,
        escalation_summary=bsti_escalation_summary,
    )

    regime_diagnostics = regime_performance_summary(
        strategy_returns=overlay_returns,
        regime=regime_table["regime"],
    )

    stress_summary = stress_window_summary(
        strategy_returns=overlay_returns,
        regime=regime_table["regime"],
        benchmark_column="passive_brazil_equity",
    )

    stress_read = stress_window_interpretation(stress_summary)

    help_hurt_summary = strategy_help_hurt_diagnostics(
        strategy_returns=overlay_returns,
        benchmark_column="passive_brazil_equity",
    )

    help_hurt_read = strategy_help_hurt_interpretation(help_hurt_summary)

    implementation_summary = implementation_drag_diagnostics(
        gross_strategy_returns=gross_overlay_returns,
        net_strategy_returns=overlay_returns,
        benchmark_column="passive_brazil_equity",
    )

    implementation_read = implementation_drag_interpretation(implementation_summary)

    option_attribution = option_overlay_attribution(
        prices=data.prices["brazil_equity"],
        returns=data.returns["brazil_equity"],
        regime=regime_table["regime"],
        maturity_days=maturity_days,
        transaction_cost_bps=5.0,
    )

    option_attribution_summary_table = option_overlay_attribution_summary(
        option_attribution
    )

    option_attribution_read = option_overlay_attribution_interpretation(
        option_attribution_summary_table
    )

    option_attribution_regime_summary = option_attribution_by_regime(
        option_attribution
    )

    option_attribution_drawdown_summary = option_attribution_by_drawdown_bucket(
        attribution=option_attribution,
        benchmark_returns=overlay_returns["passive_brazil_equity"],
    )

    option_context_read = option_attribution_context_interpretation(
        regime_summary=option_attribution_regime_summary,
        drawdown_summary=option_attribution_drawdown_summary,
    )

    performance_summary_path = PROCESSED_DATA_DIR / "baseline_performance_summary.csv"
    regime_table_path = PROCESSED_DATA_DIR / "brazil_equity_regime_table.csv"
    stress_signal_table_path = PROCESSED_DATA_DIR / "multi_asset_stress_signal_table.csv"
    stress_signal_summary_path = PROCESSED_DATA_DIR / "multi_asset_stress_signal_summary.csv"
    bsti_table_path = PROCESSED_DATA_DIR / "brazil_stress_transmission_index.csv"
    bsti_summary_path = PROCESSED_DATA_DIR / "brazil_stress_transmission_index_latest.csv"
    bsti_distribution_path = PROCESSED_DATA_DIR / "brazil_stress_transmission_index_regime_distribution.csv"
    bsti_forward_outcomes_path = PROCESSED_DATA_DIR / "bsti_forward_outcomes.csv"
    bsti_threshold_validation_path = PROCESSED_DATA_DIR / "bsti_threshold_validation.csv"
    bsti_overlay_validation_path = PROCESSED_DATA_DIR / "bsti_overlay_threshold_validation.csv"
    bsti_calibration_grid_path = PROCESSED_DATA_DIR / "bsti_calibration_grid.csv"
    bsti_best_calibration_path = PROCESSED_DATA_DIR / "bsti_best_calibration_by_horizon.csv"
    bsti_policy_returns_path = PROCESSED_DATA_DIR / "bsti_policy_overlay_returns.csv"
    bsti_policy_decisions_path = PROCESSED_DATA_DIR / "bsti_policy_decisions.csv"
    bsti_policy_selection_path = PROCESSED_DATA_DIR / "bsti_policy_selection_summary.csv"
    bsti_policy_comparison_path = PROCESSED_DATA_DIR / "bsti_policy_comparison_summary.csv"
    bsti_state_table_path = PROCESSED_DATA_DIR / "bsti_state_table.csv"
    bsti_transition_matrix_path = PROCESSED_DATA_DIR / "bsti_transition_matrix.csv"
    bsti_state_duration_path = PROCESSED_DATA_DIR / "bsti_state_duration_summary.csv"
    bsti_escalation_path = PROCESSED_DATA_DIR / "bsti_escalation_summary.csv"
    bsti_channel_transitions_path = PROCESSED_DATA_DIR / "bsti_pressure_channel_transitions.csv"
    overlay_returns_path = PROCESSED_DATA_DIR / "overlay_return_table.csv"
    overlay_summary_path = PROCESSED_DATA_DIR / "overlay_performance_summary.csv"
    data_provenance_path = PROCESSED_DATA_DIR / "data_provenance_table.csv"
    active_risk_path = PROCESSED_DATA_DIR / "active_risk_summary.csv"
    active_risk_by_regime_path = PROCESSED_DATA_DIR / "active_risk_by_regime_summary.csv"
    drawdown_depth_path = PROCESSED_DATA_DIR / "drawdown_depth_summary.csv"
    recovery_window_path = PROCESSED_DATA_DIR / "recovery_window_summary.csv"
    regime_diagnostics_path = PROCESSED_DATA_DIR / "regime_performance_summary.csv"
    stress_window_path = PROCESSED_DATA_DIR / "stress_window_summary.csv"
    help_hurt_path = PROCESSED_DATA_DIR / "strategy_help_hurt_summary.csv"
    implementation_drag_path = PROCESSED_DATA_DIR / "implementation_drag_summary.csv"
    option_attribution_path = PROCESSED_DATA_DIR / "option_overlay_attribution.csv"
    option_attribution_summary_path = PROCESSED_DATA_DIR / "option_overlay_attribution_summary.csv"
    option_attribution_regime_path = PROCESSED_DATA_DIR / "option_attribution_by_regime.csv"
    option_attribution_drawdown_path = PROCESSED_DATA_DIR / "option_attribution_by_drawdown_bucket.csv"

    performance_summary.to_csv(performance_summary_path)
    regime_table.to_csv(regime_table_path)
    stress_signal_table.to_csv(stress_signal_table_path)
    stress_signal_latest.to_csv(stress_signal_summary_path, index=False)
    bsti_table.to_csv(bsti_table_path)
    bsti_latest_summary.to_csv(bsti_summary_path, index=False)
    bsti_distribution.to_csv(bsti_distribution_path, index=False)
    overlay_returns.to_csv(overlay_returns_path)
    overlay_summary.to_csv(overlay_summary_path)
    data_provenance.to_csv(data_provenance_path, index=False)
    active_risk_summary.to_csv(active_risk_path)
    active_regime_summary.to_csv(active_risk_by_regime_path, index=False)
    drawdown_depth_summary.to_csv(drawdown_depth_path, index=False)
    recovery_window_summary.to_csv(recovery_window_path)
    bsti_forward_outcomes.to_csv(bsti_forward_outcomes_path, index=False)
    bsti_threshold_validation_table.to_csv(bsti_threshold_validation_path, index=False)
    bsti_overlay_validation_table.to_csv(bsti_overlay_validation_path, index=False)
    bsti_calibration_grid.to_csv(bsti_calibration_grid_path, index=False)
    bsti_best_calibration.to_csv(bsti_best_calibration_path, index=False)
    bsti_policy_returns.to_csv(bsti_policy_returns_path, index=True)
    bsti_policy_decisions.to_csv(bsti_policy_decisions_path, index=True)
    bsti_policy_selection.to_csv(bsti_policy_selection_path, index=False)
    bsti_policy_comparison.to_csv(bsti_policy_comparison_path, index=True)
    bsti_state_table.to_csv(bsti_state_table_path, index=True)
    bsti_transition_matrix.to_csv(bsti_transition_matrix_path, index=False)
    bsti_state_duration_summary.to_csv(bsti_state_duration_path, index=False)
    bsti_escalation_summary.to_csv(bsti_escalation_path, index=False)
    bsti_pressure_channel_transitions.to_csv(bsti_channel_transitions_path, index=False)
    regime_diagnostics.to_csv(regime_diagnostics_path, index=False)
    stress_summary.to_csv(stress_window_path)
    help_hurt_summary.to_csv(help_hurt_path)
    implementation_summary.to_csv(implementation_drag_path)
    option_attribution.to_csv(option_attribution_path, index=False)
    option_attribution_summary_table.to_csv(option_attribution_summary_path)
    option_attribution_regime_summary.to_csv(option_attribution_regime_path, index=False)
    option_attribution_drawdown_summary.to_csv(option_attribution_drawdown_path, index=False)

    start_date = data.prices.index.min().date()
    end_date = data.prices.index.max().date()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    latest_regime = regime_table["regime"].iloc[-1]
    latest_volatility = regime_table["realized_volatility"].iloc[-1]
    latest_drawdown = regime_table["drawdown"].iloc[-1]

    best_return = _safe_idxmax(overlay_summary, "annualized_return")
    best_drawdown = _safe_idxmax(overlay_summary, "max_drawdown")
    best_sharpe = _safe_idxmax(overlay_summary, "sharpe_ratio")
    worst_drawdown = _safe_idxmin(overlay_summary, "max_drawdown")
    best_information_ratio = _safe_idxmax(active_risk_summary, "information_ratio")

    decision_bias = _decision_bias(latest_regime, latest_drawdown, overlay_summary)
    shockbridge_signal = _shockbridge_signal(
        latest_regime,
        latest_volatility,
        latest_drawdown,
    )
    watch_next = _watch_next(latest_regime)

    report = f"""# BRAVO Lab Market Regime and Overlay Decision Report

**Subtitle:** Brazilian Equity Risk, Volatility Transmission, and Synthetic Protection Logic

Generated at: **{generated_at}**

Data window: **{start_date} to {end_date}**

Target report length: **34 to 38 PDF pages**

## 1. Executive Signal

**Current regime:** `{latest_regime}`

**Latest realized volatility:** {_format_percentage(latest_volatility)}

**Latest drawdown:** {_format_percentage(latest_drawdown)}

**Decision bias:** {decision_bias}

**Best information ratio versus passive:** `{best_information_ratio}`

{shockbridge_signal}

## 2. Report Map

{_report_structure()}

## 3. Portfolio Question

The core question is not whether passive equity, covered calls, collars, or
stress-aware switching are better in isolation. The correct question is
regime-dependent.

When Brazilian equity risk changes state, should the portfolio keep full beta,
sell volatility through covered calls, pay for downside protection through
collars, or switch exposure based on regime evidence?

This report gives the first reproducible answer. It measures the market state,
classifies the volatility and drawdown regime, compares synthetic overlays,
calculates active risk versus passive Brazilian equity, and turns the result
into a portfolio decision frame.

## 4. Market State

The baseline market layer tracks Brazilian equity exposure, external Brazil
exposure, global equity risk, USD/BRL, and VIX. This gives a first cross-market
view of local beta, external Brazil risk, global risk appetite, currency stress,
and volatility pressure.

This is not yet a full production model. It is a clean research base. The value
is transparency. A reviewer can inspect the assumptions, rerun the output, and
challenge the decision logic.

## 5. Data Provenance and Evidence Classification

A robust report must separate observed data from modeled signals.

The market layer uses real public market data downloaded through Yahoo Finance
with `yfinance`. The derivatives layer is synthetic. Covered call and collar
premiums are estimated through the Black-Scholes engine until real B3
listed-option chains are integrated.

This distinction matters. A real price series can support risk measurement. A
synthetic option premium can support research design. It cannot yet support live
execution decisions.

{_data_provenance_to_markdown(data_provenance)}

## 6. Regime Diagnosis

The current Brazilian equity signal sits in `{latest_regime}`.

That matters because the same overlay can behave well in one regime and poorly
in another. A covered call can create useful income in a range-bound market, but
it can also sell the recovery too cheaply. A collar can protect the book during
stress, but it can also become expensive insurance if drawdown risk fades.

The regime classifier uses realized volatility, volatility percentile, and
drawdown. It is simple by design. The point is to create an auditable baseline
before adding GARCH, MTV-GARCH, stress transmission indexes, wavelets, CCA, or
machine learning.

### Regime Snapshot

Latest classified regime: **{latest_regime}**

Latest realized volatility: **{_format_percentage(latest_volatility)}**

Latest drawdown: **{_format_percentage(latest_drawdown)}**

### Regime Distribution

{_regime_counts_to_markdown(regime_table)}

## 7. Baseline Risk Metrics

The table below gives the first risk layer across the monitored assets. It is
not a final allocation model. It is the risk map used to decide whether the
overlay discussion is taking place in a calm, fragile, or stressed environment.

{_performance_table_to_markdown(performance_summary)}

## 8. Synthetic Overlay Results

The first overlay engine compares four exposures:

- passive Brazilian equity exposure
- synthetic covered call overlay
- synthetic protective collar overlay
- stress-aware overlay switching

The engine uses a 21-trading-day rebalance approximation, synthetic
Black-Scholes option premiums, and a transaction-cost assumption of
**{transaction_cost_bps:.1f} basis points per option leg**.

The stress-aware overlay maps regimes into actions: passive exposure in calm
conditions, covered call income in fragile conditions, and collar protection in
stress or extreme-stress conditions. It does not claim live tradability. It is a
controlled research baseline before adding real B3 option chains, taxes,
liquidity, and execution constraints.

Returns in this section are approximately monthly strategy-period returns,
annualized using **{periods_per_year:.1f} periods per year**.

{_overlay_table_to_markdown(overlay_summary)}

## 9. Active Risk Diagnostics

Absolute return is not enough. A portfolio desk also needs to know whether the
overlay earns enough to justify its deviation from passive Brazilian equity.

Tracking error measures how far the overlay moves away from passive exposure.
The information ratio tests whether that active deviation is rewarded. Hit rate
shows how often the overlay beats passive. Downside hit rate is stricter. It
asks whether the overlay helps when passive exposure is already losing money.

{_active_risk_to_markdown(active_risk_summary)}

## 9. Active Risk by Regime

Full-sample tracking error is useful, but it is not enough for portfolio
governance. A strategy can look acceptable across the whole sample while creating
too much active risk in a specific market state.

This diagnostic shows where each overlay creates tracking error versus passive
Brazilian equity exposure: calm markets, fragile markets, stress markets, or
extreme-stress markets.

{_active_risk_by_regime_to_markdown(active_regime_summary)}

### Active Risk by Regime Interpretation

{active_regime_read}

## 10. Multi-Asset Stress Signals

The first regime layer is built from local Brazilian equity behavior. That is
useful, but incomplete. A portfolio stress system should also look outside the
local price series.

This section adds external Brazil exposure, global equity pressure, USD/BRL
pressure, and VIX pressure to create a broader multi-asset stress dashboard. It
does not forecast markets. It identifies where pressure is currently coming
from.

{_stress_signal_summary_to_markdown(stress_signal_latest)}

### Multi-Asset Stress Interpretation

{stress_signal_read}

## 11. Brazil Stress Transmission Index

The multi-asset stress dashboard shows the individual pressure inputs. The Brazil
Stress Transmission Index converts those inputs into a formal composite index
from 0 to 100.

The purpose is portfolio governance. The index gives the research a single
monitorable stress state while preserving the underlying channels that explain
where pressure is coming from.

### Latest BSTI State

{_bsti_summary_to_markdown(bsti_latest_summary)}

### Historical BSTI Regime Distribution

{_bsti_regime_distribution_to_markdown(bsti_distribution)}

### BSTI Interpretation

{bsti_read}

## 12. BSTI Threshold Validation

A stress index is only useful if its thresholds connect to portfolio-relevant
outcomes. This validation layer tests whether BSTI levels are associated with
future benchmark losses, future drawdowns, and overlay behavior when stress is
already elevated.

This does not claim forecasting power. It tests whether BSTI is informative
enough to support portfolio-governance discussion.

### BSTI Thresholds versus Future Outcomes

{_bsti_threshold_validation_to_markdown(bsti_threshold_validation_table)}

### Overlay Behavior When BSTI Is Elevated

{_bsti_overlay_validation_to_markdown(bsti_overlay_validation_table)}

### BSTI Validation Interpretation

{bsti_validation_read}

## 13. BSTI Threshold Calibration

The first BSTI threshold validation tests a fixed index structure. This
calibration layer asks a more demanding question: does the stress index behave
better under alternative thresholds and channel weights?

The point is not to overfit the index. The point is to test whether the chosen
structure is robust enough for portfolio-governance discussion.

### Calibration Grid

{_bsti_calibration_grid_to_markdown(bsti_calibration_grid)}

### Best Calibration by Horizon

{_bsti_best_calibration_to_markdown(bsti_best_calibration)}

### Calibration Interpretation

{bsti_calibration_read}

## 14. BSTI Overlay Policy Selection

The BSTI policy layer converts the stress index into an explicit portfolio
action. This is where the project moves from diagnosis to governance.

The rule is intentionally simple:

- low BSTI: remain in passive Brazil equity exposure
- medium BSTI: use covered calls to collect option premium
- high BSTI: use collars to prioritize downside control

This does not claim to forecast returns. It tests whether a transparent
stress signal can discipline overlay selection across passive exposure,
covered calls, collars, and the existing local-regime stress-aware overlay.

### Policy Selection Summary

{_bsti_policy_selection_to_markdown(bsti_policy_selection)}

### Policy Performance Comparison

{_bsti_policy_comparison_to_markdown(bsti_policy_comparison)}

### Policy Interpretation

{bsti_policy_read}

## 15. BSTI Signal Persistence and State Transitions

A stress signal is not useful only because it moves. It is useful when it
persists long enough to support a decision process.

This section tests whether the Brazil Stress Transmission Index behaves like a
governance signal rather than a random dashboard number. It classifies each
BSTI observation into normal, warning, or stress states, then studies transition
probabilities, state duration, warning-to-stress escalation, and dominant
pressure-channel rotation.

### BSTI State Transition Matrix

{_bsti_transition_matrix_to_markdown(bsti_transition_matrix)}

### BSTI State Duration Summary

{_bsti_state_duration_to_markdown(bsti_state_duration_summary)}

### Warning-to-Stress Escalation

{_bsti_escalation_to_markdown(bsti_escalation_summary)}

### Dominant Pressure-Channel Transitions

{_bsti_channel_transitions_to_markdown(bsti_pressure_channel_transitions)}

### Transition Interpretation

{bsti_transition_read}

## 16. Drawdown and Recovery Diagnostics

Drawdown diagnostics ask whether the overlay helps at different levels of
benchmark pain. Recovery diagnostics ask the uncomfortable second question:
does the hedge damage the portfolio when the market starts rebounding?

This matters because a protective overlay can be useful during the fall and
still become expensive during the recovery.

### Drawdown-Depth Summary

{_drawdown_depth_to_markdown(drawdown_depth_summary)}

### Recovery-Window Summary

{_recovery_window_to_markdown(recovery_window_summary)}

### Drawdown-Recovery Interpretation

{drawdown_recovery_read}

## 17. Regime and Stress-Window Diagnostics

Full-sample metrics can hide the real question. A strategy that looks strong in
normal conditions may fail when the benchmark is under pressure.

This section tests the overlay behavior by regime and during stress windows. The
goal is to identify whether the strategy helps when protection, income discipline,
and active-risk control matter most.

### Regime-Level Performance

{_regime_performance_to_markdown(regime_diagnostics)}

### Stress-Window Summary

{_stress_window_to_markdown(stress_summary)}

### Stress-Window Interpretation

{stress_read}

## 18. Strategy Help-Hurt Diagnostics

The help-hurt diagnostic explains the trade-off behind each overlay. A strategy
can protect the downside and still hurt the portfolio if it gives away too much
rebound. It can also improve income while failing to protect the book when the
benchmark is already falling.

This section separates the periods where each overlay adds active value from the
periods where it creates drag versus passive Brazilian equity.

{_help_hurt_to_markdown(help_hurt_summary)}

### Help-Hurt Interpretation

{help_hurt_read}

## 19. Implementation Drag Diagnostics

The implementation-drag diagnostic separates the gross overlay signal from the
net result after transaction costs. This matters because an overlay can look
useful before costs and still fail after realistic rebalancing drag.

The diagnostic does not yet decompose every option leg into premium income,
payoff effect, and moneyness attribution. It is the intermediate institutional
layer showing whether the overlay signal survives implementation.

{_implementation_drag_to_markdown(implementation_summary)}

### Implementation Interpretation

{implementation_read}

## 20. Option Overlay Attribution

This attribution layer explains why the synthetic option overlay worked or
failed. It separates the model-implied return into premium income, protection
cost, payoff effect, implementation drag, and net overlay effect.

This is not real B3 option-chain attribution. It is model-implied attribution
based on the synthetic Black-Scholes overlay engine used in this project. That
disclosure is important because it keeps the research honest while still making
the derivatives logic inspectable.

{_option_attribution_to_markdown(option_attribution_summary_table)}

### Option Attribution Interpretation

{option_attribution_read}

## 21. Option Attribution by Regime and Drawdown Bucket

The previous attribution table explains the average option overlay effect. This
section asks where that effect appears. Premium income, protection cost, payoff
effect, and implementation drag do not matter equally in every market state.

This layer separates the synthetic option attribution by regime and by benchmark
drawdown bucket. The goal is to identify whether the strategy is earning income
in calm markets, protecting in stress, paying off in deep drawdowns, or creating
drag near market peaks.

### Option Attribution by Regime

{_option_attribution_context_to_markdown(option_attribution_regime_summary, "regime")}

### Option Attribution by Drawdown Bucket

{_option_attribution_context_to_markdown(option_attribution_drawdown_summary, "drawdown_bucket")}

### Option Context Interpretation

{option_context_read}

## 22. Overlay Decision Matrix

{_strategy_decision_matrix()}

## 23. Strategy Trade-Off

**Best annualized return:** `{best_return}`

**Best drawdown profile:** `{best_drawdown}`

**Best Sharpe profile:** `{best_sharpe}`

**Best information ratio versus passive:** `{best_information_ratio}`

**Weakest drawdown profile:** `{worst_drawdown}`

The decision is not to chase the highest return. The decision is to match the
overlay to the regime and check whether active risk is rewarded.

Passive equity keeps the cleanest upside but carries the full left tail. Covered
calls convert part of upside into premium income, which can help in sideways or
moderately volatile markets. Collars give the book a defined protection logic,
but their cost and upside cap must be justified by the current risk state.
Stress-aware switching adds discipline, but only if the regime signal is stable
enough to avoid unnecessary turnover.

## 24. Results SWOT

How to cope with the signal before turning it into a portfolio action.

{_results_swot()}

## 25. ShockBridge Transmission Read

Brazilian equity does not trade in isolation. The book can be hit through local
rates, fiscal repricing, FX pressure, global volatility, commodity shocks, and
external risk appetite.

This first version does not model every channel. It builds the base layer that
future ShockBridge modules can extend into a formal Brazil Stress Transmission
Index.

The key insight is simple: volatility is not only a number. It is a carrier of
stress. When volatility rises with drawdown, the book is not just moving. It is
absorbing transmission.

## 26. What To Watch Next

{watch_next}

The next model version should not simply add complexity. It should improve the
decision. The immediate test is whether transaction costs, tracking error, and
stress subperiod performance confirm or weaken the current overlay ranking.

## 27. What Would Break This View

This baseline view should be challenged if one of the following happens:

1. The regime classifier changes but overlay results do not respond.
2. Synthetic option premiums diverge too far from real B3 listed-option behavior.
3. Transaction costs erase the apparent benefit of the overlay.
4. The collar improves drawdown but destroys too much participation.
5. The covered call improves income but systematically sells the strongest rebounds.
6. The model performs well in the full sample but fails in stress subperiods.
7. The information ratio is positive in the full sample but weak during stress windows.
8. Tracking error rises without clear drawdown reduction or active return compensation.

## 28. Model Limits and Governance

This report is intentionally clear about what it does not prove.

- Yahoo Finance data is used as the baseline public-data source.
- No real B3 option-chain data is used yet.
- Option premiums are synthetic Black-Scholes approximations.
- Transaction costs, taxes, spreads, and liquidity constraints are not included yet.
- GARCH and MTV-GARCH are not yet active in this report.
- The regime classifier is transparent but not final.
- Active risk diagnostics are useful but still require stress-window validation.
- This is research infrastructure, not investment advice.

## 29. Generated Evidence Files

- `{performance_summary_path}`
- `{regime_table_path}`
- `{stress_signal_table_path}`
- `{stress_signal_summary_path}`
- `{bsti_table_path}`
- `{bsti_summary_path}`
- `{bsti_distribution_path}`
- `{bsti_forward_outcomes_path}`
- `{bsti_threshold_validation_path}`
- `{bsti_overlay_validation_path}`
- `{bsti_calibration_grid_path}`
- `{bsti_best_calibration_path}`
- `{bsti_policy_returns_path}`
- `{bsti_policy_decisions_path}`
- `{bsti_policy_selection_path}`
- `{bsti_policy_comparison_path}`
- `{bsti_state_table_path}`
- `{bsti_transition_matrix_path}`
- `{bsti_state_duration_path}`
- `{bsti_escalation_path}`
- `{bsti_channel_transitions_path}`
- `{overlay_returns_path}`
- `{overlay_summary_path}`
- `{data_provenance_path}`
- `{active_risk_path}`
- `{active_risk_by_regime_path}`
- `{drawdown_depth_path}`
- `{recovery_window_path}`
- `{regime_diagnostics_path}`
- `{stress_window_path}`
- `{help_hurt_path}`
- `{implementation_drag_path}`
- `{option_attribution_path}`
- `{option_attribution_summary_path}`
- `{option_attribution_regime_path}`
- `{option_attribution_drawdown_path}`
- `{output_path}`

## 30. Next Upgrade

The next upgrade should turn this from a stress-window decision memo into a
more realistic implementation framework:

1. test alternative transaction-cost levels
2. validate synthetic attribution against real B3 option-chain data when available
3. connect BSTI transition states to overlay-policy confirmation rules
4. add stress-signal decay and false-alarm diagnostics
5. prepare the path for GARCH, MTV-GARCH, and portfolio-governance scenario testing

## Research Use Only

This report is generated by BRAVO Lab for reproducible research and portfolio
discussion. It is not a trading recommendation, not a solicitation, and not a
production investment model.
"""

    report_figure_paths = build_report_figure_set(
        processed_dir=PROCESSED_DATA_DIR,
        figures_dir=REPORTS_DIR / "figures",
    )

    report_figure_gallery = figure_markdown_gallery(report_figure_paths)

    report = report.replace(
        "## 1. Executive Summary",
        f"## Premium Visual Evidence Layer\n\n{report_figure_gallery}\n\n## 1. Executive Summary",
        1,
    )

    output_path.write_text(report, encoding="utf-8")

    return output_path


if __name__ == "__main__":
    path = generate_baseline_report()
    print(f"Baseline report generated: {path}")
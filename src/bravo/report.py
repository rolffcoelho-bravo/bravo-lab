
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

from bravo.config import BASELINE_REPORT_PATH, PROCESSED_DATA_DIR, REPORTS_DIR, TICKERS
from bravo.data import load_market_data
from bravo.diagnostics import (
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
| 10 | Regime and Stress Diagnostics | Tests whether the overlay helps when market pressure rises |
| 11 | Strategy Help-Hurt Diagnostics | Explains when each overlay adds value or creates drag |
| 12 | Implementation Drag Diagnostics | Separates gross signal, cost drag, and net overlay effect |
| 13 | Overlay Decision Matrix | When each strategy is useful or dangerous |
| 14 to 15 | Results SWOT | How to cope with the signal before portfolio action |
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

    performance_summary_path = PROCESSED_DATA_DIR / "baseline_performance_summary.csv"
    regime_table_path = PROCESSED_DATA_DIR / "brazil_equity_regime_table.csv"
    overlay_returns_path = PROCESSED_DATA_DIR / "overlay_return_table.csv"
    overlay_summary_path = PROCESSED_DATA_DIR / "overlay_performance_summary.csv"
    data_provenance_path = PROCESSED_DATA_DIR / "data_provenance_table.csv"
    active_risk_path = PROCESSED_DATA_DIR / "active_risk_summary.csv"
    active_risk_by_regime_path = PROCESSED_DATA_DIR / "active_risk_by_regime_summary.csv"
    regime_diagnostics_path = PROCESSED_DATA_DIR / "regime_performance_summary.csv"
    stress_window_path = PROCESSED_DATA_DIR / "stress_window_summary.csv"
    help_hurt_path = PROCESSED_DATA_DIR / "strategy_help_hurt_summary.csv"
    implementation_drag_path = PROCESSED_DATA_DIR / "implementation_drag_summary.csv"

    performance_summary.to_csv(performance_summary_path)
    regime_table.to_csv(regime_table_path)
    overlay_returns.to_csv(overlay_returns_path)
    overlay_summary.to_csv(overlay_summary_path)
    data_provenance.to_csv(data_provenance_path, index=False)
    active_risk_summary.to_csv(active_risk_path)
    active_regime_summary.to_csv(active_risk_by_regime_path, index=False)
    regime_diagnostics.to_csv(regime_diagnostics_path, index=False)
    stress_summary.to_csv(stress_window_path)
    help_hurt_summary.to_csv(help_hurt_path)
    implementation_summary.to_csv(implementation_drag_path)

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

Target report length: **17 to 19 PDF pages**

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

## 10. Regime and Stress-Window Diagnostics

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

## 11. Strategy Help-Hurt Diagnostics

The help-hurt diagnostic explains the trade-off behind each overlay. A strategy
can protect the downside and still hurt the portfolio if it gives away too much
rebound. It can also improve income while failing to protect the book when the
benchmark is already falling.

This section separates the periods where each overlay adds active value from the
periods where it creates drag versus passive Brazilian equity.

{_help_hurt_to_markdown(help_hurt_summary)}

### Help-Hurt Interpretation

{help_hurt_read}

## 12. Implementation Drag Diagnostics

The implementation-drag diagnostic separates the gross overlay signal from the
net result after transaction costs. This matters because an overlay can look
useful before costs and still fail after realistic rebalancing drag.

The diagnostic does not yet decompose every option leg into premium income,
payoff effect, and moneyness attribution. It is the intermediate institutional
layer showing whether the overlay signal survives implementation.

{_implementation_drag_to_markdown(implementation_summary)}

### Implementation Interpretation

{implementation_read}

## 13. Overlay Decision Matrix

{_strategy_decision_matrix()}

## 14. Strategy Trade-Off

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

## 15. Results SWOT

How to cope with the signal before turning it into a portfolio action.

{_results_swot()}

## 16. ShockBridge Transmission Read

Brazilian equity does not trade in isolation. The book can be hit through local
rates, fiscal repricing, FX pressure, global volatility, commodity shocks, and
external risk appetite.

This first version does not model every channel. It builds the base layer that
future ShockBridge modules can extend into a formal Brazil Stress Transmission
Index.

The key insight is simple: volatility is not only a number. It is a carrier of
stress. When volatility rises with drawdown, the book is not just moving. It is
absorbing transmission.

## 17. What To Watch Next

{watch_next}

The next model version should not simply add complexity. It should improve the
decision. The immediate test is whether transaction costs, tracking error, and
stress subperiod performance confirm or weaken the current overlay ranking.

## 18. What Would Break This View

This baseline view should be challenged if one of the following happens:

1. The regime classifier changes but overlay results do not respond.
2. Synthetic option premiums diverge too far from real B3 listed-option behavior.
3. Transaction costs erase the apparent benefit of the overlay.
4. The collar improves drawdown but destroys too much participation.
5. The covered call improves income but systematically sells the strongest rebounds.
6. The model performs well in the full sample but fails in stress subperiods.
7. The information ratio is positive in the full sample but weak during stress windows.
8. Tracking error rises without clear drawdown reduction or active return compensation.

## 19. Model Limits and Governance

This report is intentionally clear about what it does not prove.

- Yahoo Finance data is used as the baseline public-data source.
- No real B3 option-chain data is used yet.
- Option premiums are synthetic Black-Scholes approximations.
- Transaction costs, taxes, spreads, and liquidity constraints are not included yet.
- GARCH and MTV-GARCH are not yet active in this report.
- The regime classifier is transparent but not final.
- Active risk diagnostics are useful but still require stress-window validation.
- This is research infrastructure, not investment advice.

## 20. Generated Evidence Files

- `{performance_summary_path}`
- `{regime_table_path}`
- `{overlay_returns_path}`
- `{overlay_summary_path}`
- `{data_provenance_path}`
- `{active_risk_path}`
- `{active_risk_by_regime_path}`
- `{regime_diagnostics_path}`
- `{stress_window_path}`
- `{help_hurt_path}`
- `{implementation_drag_path}`
- `{output_path}`

## 21. Next Upgrade

The next upgrade should turn this from a stress-window decision memo into a
more realistic implementation framework:

1. test alternative transaction-cost levels
2. extend active risk into drawdown-depth buckets and recovery windows
3. decompose option overlays into premium income, payoff effect, and moneyness attribution
4. integrate real B3 option-chain data when available
5. prepare the path for GARCH, MTV-GARCH, and Brazil Stress Transmission Index integration

## Research Use Only

This report is generated by BRAVO Lab for reproducible research and portfolio
discussion. It is not a trading recommendation, not a solicitation, and not a
production investment model.
"""

    output_path.write_text(report, encoding="utf-8")

    return output_path


if __name__ == "__main__":
    path = generate_baseline_report()
    print(f"Baseline report generated: {path}")
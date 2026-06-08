"""
Baseline report generation for BRAVO Lab.

This module creates the first executable output of the project:
a simple decision-oriented markdown report using market prices, returns,
performance metrics, volatility, drawdown, baseline regime classification,
and synthetic derivatives overlay prototypes.

This is not a trading recommendation. It is a reproducible research output.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from bravo.config import BASELINE_REPORT_PATH, PROCESSED_DATA_DIR, REPORTS_DIR
from bravo.data import load_market_data
from bravo.metrics import summarize_performance
from bravo.strategies import build_overlay_return_table
from bravo.volatility import build_baseline_regime_table


def _format_percentage(value: float) -> str:
    """
    Format a number as percentage for report readability.
    """
    if pd.isna(value):
        return "NA"
    return f"{value:.2%}"


def _format_number(value: float) -> str:
    """
    Format a floating-point number for report readability.
    """
    if pd.isna(value):
        return "NA"
    return f"{value:.3f}"


def _performance_table_to_markdown(summary: pd.DataFrame) -> str:
    """
    Convert the daily performance summary into a markdown table without requiring
    optional pandas dependencies such as tabulate.
    """
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
    """
    Convert regime counts into a markdown table.
    """
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
    """
    Calculate maximum drawdown from periodic strategy returns.
    """
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
    """
    Summarize non-daily strategy returns.

    The derivatives overlay engine currently generates approximately monthly
    21-trading-day period returns. This function annualizes those returns using
    the correct number of periods per year instead of treating them as daily.
    """
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
        annualized_return = (
            cumulative_return ** (1 / years) - 1 if years > 0 else np.nan
        )
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
    """
    Convert overlay strategy summary into markdown.
    """
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


def generate_baseline_report(output_path: Path = BASELINE_REPORT_PATH) -> Path:
    """
    Generate the baseline markdown report.

    Returns
    -------
    pathlib.Path
        Path to the generated report.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    data = load_market_data()
    performance_summary = summarize_performance(data.returns)

    if "brazil_equity" not in data.returns.columns:
        raise KeyError("Expected 'brazil_equity' in returns. Check ticker configuration.")

    regime_table = build_baseline_regime_table(data.returns["brazil_equity"])

    maturity_days = 21
    periods_per_year = 252 / maturity_days

    overlay_returns = build_overlay_return_table(
        prices=data.prices["brazil_equity"],
        returns=data.returns["brazil_equity"],
        maturity_days=maturity_days,
    )

    overlay_summary = _summarize_periodic_strategy_returns(
        returns=overlay_returns,
        periods_per_year=periods_per_year,
    )

    performance_summary_path = PROCESSED_DATA_DIR / "baseline_performance_summary.csv"
    regime_table_path = PROCESSED_DATA_DIR / "brazil_equity_regime_table.csv"
    overlay_returns_path = PROCESSED_DATA_DIR / "overlay_return_table.csv"
    overlay_summary_path = PROCESSED_DATA_DIR / "overlay_performance_summary.csv"

    performance_summary.to_csv(performance_summary_path)
    regime_table.to_csv(regime_table_path)
    overlay_returns.to_csv(overlay_returns_path)
    overlay_summary.to_csv(overlay_summary_path)

    start_date = data.prices.index.min().date()
    end_date = data.prices.index.max().date()
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    latest_regime = regime_table["regime"].iloc[-1]
    latest_volatility = regime_table["realized_volatility"].iloc[-1]
    latest_drawdown = regime_table["drawdown"].iloc[-1]

    report = f"""# BRAVO Lab Baseline Report

Generated at: **{generated_at}**

Data window: **{start_date} to {end_date}**

## Purpose

This report is an executable output of BRAVO Lab. It downloads baseline market
data, calculates returns, summarizes risk and performance metrics, classifies a
transparent volatility/drawdown regime for Brazilian equity exposure, and tests
the first synthetic derivatives overlay prototypes.

This is not a trading recommendation. It is a reproducible research output
designed to support portfolio discussion and future model development.

## Assets

The baseline configuration currently tracks:

- `brazil_equity`: BOVA11 / Brazilian equity proxy
- `brazil_external`: EWZ / external Brazil ETF proxy
- `global_equity`: SPY / global equity benchmark
- `fx_usdbrl`: USD/BRL exchange-rate proxy
- `vix`: VIX volatility index

## Baseline Performance Summary

{_performance_table_to_markdown(performance_summary)}

## Brazilian Equity Regime Snapshot

Latest classified regime: **{latest_regime}**

Latest realized volatility: **{_format_percentage(latest_volatility)}**

Latest drawdown: **{_format_percentage(latest_drawdown)}**

## Regime Distribution

{_regime_counts_to_markdown(regime_table)}

## Synthetic Derivatives Overlay Prototype

This report now includes the first synthetic overlay comparison:

- passive Brazilian equity exposure
- synthetic covered call overlay
- synthetic protective collar overlay

The overlay engine uses a 21-trading-day rebalance approximation and synthetic
Black-Scholes option premiums. This is a research baseline only. It does not yet
use real B3 option-chain data, transaction costs, taxes, liquidity filters, or
execution constraints.

## Overlay Strategy Summary

Returns in this section are approximately monthly strategy-period returns,
annualized using **{periods_per_year:.1f} periods per year**.

{_overlay_table_to_markdown(overlay_summary)}

## Interpretation

The current regime classifier is intentionally simple. It uses realized
volatility, volatility percentile, and drawdown to classify Brazilian equity
conditions into calm, fragile, stress, and extreme-stress states.

The derivatives overlay layer is also intentionally simple. Its purpose is to
create a transparent baseline before introducing transaction costs, tracking
error discipline, real option-chain data, GARCH, MTV-GARCH, the Brazil Stress
Transmission Index, CCA, wavelets, or ML-based regime classification.

## Generated Files

- `{performance_summary_path}`
- `{regime_table_path}`
- `{overlay_returns_path}`
- `{overlay_summary_path}`
- `{output_path}`

## Current Limitations

- Yahoo Finance data is used as a baseline public-data source.
- No real B3 option-chain data is used yet.
- Option premiums are synthetic Black-Scholes approximations.
- Transaction costs, taxes, spreads, and liquidity constraints are not included yet.
- GARCH and MTV-GARCH are not yet implemented in this report.
- The regime classifier is a transparent baseline, not a final model.

## Next Development Step

The next phase should improve the derivatives overlay engine with:

1. transaction-cost assumptions
2. tracking error versus passive Brazilian equity
3. stress-aware switching between passive, covered call, and collar overlays
4. diagnostics showing when each strategy helps or hurts
5. model-governance notes for portfolio review
"""

    output_path.write_text(report, encoding="utf-8")

    return output_path


if __name__ == "__main__":
    path = generate_baseline_report()
    print(f"Baseline report generated: {path}")
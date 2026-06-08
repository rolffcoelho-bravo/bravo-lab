"""
Baseline report generation for BRAVO Lab.

This module creates the first executable output of the project:
a simple decision-oriented markdown report using market prices, returns,
performance metrics, volatility, drawdown, and baseline regime classification.

This is not a trading recommendation. It is a reproducible research output.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from bravo.config import BASELINE_REPORT_PATH, PROCESSED_DATA_DIR, REPORTS_DIR
from bravo.data import load_market_data
from bravo.metrics import summarize_performance
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
    Convert the performance summary into a markdown table without requiring
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
    counts = regime_table["regime"].value_counts().rename_axis("regime").reset_index(name="observations")

    lines = [
        "| Regime | Observations | Share |",
        "| --- | ---: | ---: |",
    ]

    total = counts["observations"].sum()

    for _, row in counts.iterrows():
        share = row["observations"] / total if total else 0
        lines.append(
            f"| {row['regime']} | {int(row['observations'])} | {share:.2%} |"
        )

    return "\n".join(lines)


def generate_baseline_report(output_path: Path = BASELINE_REPORT_PATH) -> Path:
    """
    Generate the first baseline markdown report.

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
        raise KeyError(
            "Expected 'brazil_equity' in returns. Check ticker configuration."
        )

    regime_table = build_baseline_regime_table(data.returns["brazil_equity"])

    performance_summary_path = PROCESSED_DATA_DIR / "baseline_performance_summary.csv"
    regime_table_path = PROCESSED_DATA_DIR / "brazil_equity_regime_table.csv"

    performance_summary.to_csv(performance_summary_path)
    regime_table.to_csv(regime_table_path)

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

This report is the first executable output of BRAVO Lab. It downloads baseline
market data, calculates returns, summarizes risk and performance metrics, and
classifies a transparent volatility/drawdown regime for Brazilian equity exposure.

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

## Interpretation

The current regime classifier is intentionally simple. It uses realized volatility,
volatility percentile, and drawdown to classify Brazilian equity conditions into
calm, fragile, stress, and extreme-stress states.

The objective is to create a transparent baseline before introducing more
advanced layers such as GARCH, MTV-GARCH, the Brazil Stress Transmission Index,
CCA, wavelets, or ML-based regime classification.

## Generated Files

- `{performance_summary_path}`
- `{regime_table_path}`
- `{output_path}`

## Current Limitations

- Yahoo Finance data is used as a baseline public-data source.
- No real B3 option-chain data is used yet.
- Covered call and collar strategy backtests are planned for later phases.
- GARCH and MTV-GARCH are not yet implemented in this report.
- The regime classifier is a transparent baseline, not a final model.

## Next Development Step

The next phase should implement the first derivatives overlay backtest:

1. passive Brazilian equity benchmark
2. synthetic covered call overlay
3. protective collar overlay
4. transaction-cost assumptions
5. tracking error and drawdown comparison
"""

    output_path.write_text(report, encoding="utf-8")

    return output_path


if __name__ == "__main__":
    path = generate_baseline_report()
    print(f"Baseline report generated: {path}")
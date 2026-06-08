"""
Institutional report generation for BRAVO Lab.

This module turns the BRAVO Lab baseline pipeline into a decision memo:
market state, regime diagnosis, overlay trade-off, results SWOT, decision bias,
model limits, and next risk signals.

The report is written for portfolio review. It is not a trading recommendation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from bravo.config import BASELINE_REPORT_PATH, PROCESSED_DATA_DIR, REPORTS_DIR
from bravo.data import load_market_data
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
| Covered Call | Elevated volatility, range-bound market, income objective | Upside is capped | Use when premium harvesting matters more than full upside capture |
| Collar | Stress regime, drawdown pressure, capital preservation | Protection cost and capped upside | Use when left-tail control matters more than return maximization |
| Future Stress-Aware Overlay | Regime-dependent switching | Model risk | Use only after validation, costs, and governance checks |"""


def _results_swot() -> str:
    return """This SWOT does not evaluate BRAVO Lab as a business project. It evaluates the current result as a portfolio decision signal.

The purpose is simple: separate what the model already shows from what still needs proof.

| Dimension | Current Reading | Portfolio Meaning |
| --- | --- | --- |
| Strengths | The report connects market state, regime classification, risk metrics, and synthetic overlay performance in one reproducible pipeline. | The decision maker can compare passive exposure, covered call income, and collar protection under the same data window instead of reading each strategy in isolation. |
| Weaknesses | The overlay premiums are synthetic. Real B3 option-chain behavior, liquidity, spreads, taxes, and execution costs are not yet included. | The current ranking should not be treated as live tradable evidence. It is a research signal that needs market microstructure validation. |
| Opportunities | The framework creates a path toward regime-aware overlay allocation. It can evolve from static comparison into a decision engine that changes exposure as volatility and drawdown conditions shift. | The strongest future use is not picking one permanent strategy. The value is learning when to hold beta, harvest premium, or buy protection. |
| Threats | The model can overstate strategy quality if synthetic option prices are too clean, if transaction costs are ignored, or if full-sample performance hides stress-period failure. | The main risk is false confidence. A premium-looking result becomes dangerous if it is not tested across stress windows, costs, and real option data. |

### SWOT Interpretation

The main strength is integration. The report does not leave the portfolio reviewer with isolated metrics. It links regime, risk, and overlay behavior.

The main weakness is tradability. Synthetic option pricing is useful for building the research engine, but it is not enough for real portfolio deployment.

The main opportunity is regime switching. A static covered call or collar strategy is too rigid for Brazilian markets. The more valuable question is when the book should shift from participation to income to protection.

The main threat is clean-model illusion. A strategy can look strong before costs, spreads, liquidity, and stress subperiods. The next version must attack that weakness directly."""


def _report_structure() -> str:
    return """| PDF Page Target | Section | Decision Purpose |
| ---: | --- | --- |
| 1 | Executive Signal | Current regime, decision bias, and portfolio read |
| 2 | Portfolio Question | What the framework is trying to decide |
| 3 | Market State | Cross-market context for Brazil exposure |
| 4 | Regime Diagnosis | Volatility, drawdown, and current regime |
| 5 | Baseline Risk Metrics | Return, risk, Sharpe, drawdown, VaR, CVaR |
| 6 | Synthetic Overlay Results | Passive versus covered call versus collar |
| 7 | Overlay Decision Matrix | When each strategy is useful or dangerous |
| 8 to 9 | Results SWOT | How to cope with the signal before portfolio action |
| 10 | ShockBridge Transmission Read | How stress moves into the book |
| 11 | What To Watch Next | Confirmation signals and warning signals |
| 12 | Model Limits and Evidence Files | What is proven, what is not, and what comes next |"""


def generate_baseline_report(output_path: Path = BASELINE_REPORT_PATH) -> Path:
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
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    latest_regime = regime_table["regime"].iloc[-1]
    latest_volatility = regime_table["realized_volatility"].iloc[-1]
    latest_drawdown = regime_table["drawdown"].iloc[-1]

    best_return = _safe_idxmax(overlay_summary, "annualized_return")
    best_drawdown = _safe_idxmax(overlay_summary, "max_drawdown")
    best_sharpe = _safe_idxmax(overlay_summary, "sharpe_ratio")
    worst_drawdown = _safe_idxmin(overlay_summary, "max_drawdown")

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

Target report length: **10 to 12 PDF pages**

## 1. Executive Signal

**Current regime:** `{latest_regime}`

**Latest realized volatility:** {_format_percentage(latest_volatility)}

**Latest drawdown:** {_format_percentage(latest_drawdown)}

**Decision bias:** {decision_bias}

{shockbridge_signal}

## 2. Report Map

{_report_structure()}

## 3. Portfolio Question

The core question is not whether passive equity, covered calls, or collars are
better in isolation. The correct question is regime-dependent.

When Brazilian equity risk changes state, should the portfolio keep full beta,
sell volatility through covered calls, or pay for downside protection through
collars?

This report gives the first reproducible answer. It measures the market state,
classifies the volatility and drawdown regime, compares synthetic overlays, and
turns the result into a portfolio decision frame.

## 4. Market State

The baseline market layer tracks Brazilian equity exposure, external Brazil
exposure, global equity risk, USD/BRL, and VIX. This gives a first cross-market
view of local beta, external Brazil risk, global risk appetite, currency stress,
and volatility pressure.

This is not yet a full production model. It is a clean research base. The value
is transparency. A reviewer can inspect the assumptions, rerun the output, and
challenge the decision logic.

## 5. Regime Diagnosis

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

## 6. Baseline Risk Metrics

The table below gives the first risk layer across the monitored assets. It is
not a final allocation model. It is the risk map used to decide whether the
overlay discussion is taking place in a calm, fragile, or stressed environment.

{_performance_table_to_markdown(performance_summary)}

## 7. Synthetic Overlay Results

The first overlay engine compares three exposures:

- passive Brazilian equity exposure
- synthetic covered call overlay
- synthetic protective collar overlay

The engine uses a 21-trading-day rebalance approximation and synthetic
Black-Scholes option premiums. It does not claim live tradability. It is a
controlled research baseline before adding real B3 option chains, transaction
costs, taxes, liquidity, and execution constraints.

Returns in this section are approximately monthly strategy-period returns,
annualized using **{periods_per_year:.1f} periods per year**.

{_overlay_table_to_markdown(overlay_summary)}

## 8. Overlay Decision Matrix

{_strategy_decision_matrix()}

## 9. Strategy Trade-Off

**Best annualized return:** `{best_return}`

**Best drawdown profile:** `{best_drawdown}`

**Best Sharpe profile:** `{best_sharpe}`

**Weakest drawdown profile:** `{worst_drawdown}`

The decision is not to chase the highest return. The decision is to match the
overlay to the regime.

Passive equity keeps the cleanest upside but carries the full left tail. Covered
calls convert part of upside into premium income, which can help in sideways or
moderately volatile markets. Collars give the book a defined protection logic,
but their cost and upside cap must be justified by the current risk state.

## 10. Results SWOT

How to cope with the signal before turning it into a portfolio action.

{_results_swot()}

## 11. ShockBridge Transmission Read

Brazilian equity does not trade in isolation. The book can be hit through local
rates, fiscal repricing, FX pressure, global volatility, commodity shocks, and
external risk appetite.

This first version does not model every channel. It builds the base layer that
future ShockBridge modules can extend into a formal Brazil Stress Transmission
Index.

The key insight is simple: volatility is not only a number. It is a carrier of
stress. When volatility rises with drawdown, the book is not just moving. It is
absorbing transmission.

## 12. What To Watch Next

{watch_next}

The next model version should not simply add complexity. It should improve the
decision. The immediate test is whether transaction costs, tracking error, and
stress subperiod performance confirm or weaken the current overlay ranking.

## 13. What Would Break This View

This baseline view should be challenged if one of the following happens:

1. The regime classifier changes but overlay results do not respond.
2. Synthetic option premiums diverge too far from real B3 listed-option behavior.
3. Transaction costs erase the apparent benefit of the overlay.
4. The collar improves drawdown but destroys too much participation.
5. The covered call improves income but systematically sells the strongest rebounds.
6. The model performs well in the full sample but fails in stress subperiods.

## 14. Model Limits and Governance

This report is intentionally clear about what it does not prove.

- Yahoo Finance data is used as the baseline public-data source.
- No real B3 option-chain data is used yet.
- Option premiums are synthetic Black-Scholes approximations.
- Transaction costs, taxes, spreads, and liquidity constraints are not included yet.
- GARCH and MTV-GARCH are not yet active in this report.
- The regime classifier is transparent but not final.
- This is research infrastructure, not investment advice.

## 15. Generated Evidence Files

- `{performance_summary_path}`
- `{regime_table_path}`
- `{overlay_returns_path}`
- `{overlay_summary_path}`
- `{output_path}`

## 16. Next Upgrade

The next upgrade should turn this from a static overlay comparison into a
stress-aware decision engine:

1. add transaction-cost assumptions
2. calculate tracking error versus passive Brazilian equity
3. add stress-aware switching between passive, covered call, and collar overlays
4. isolate stress subperiod performance
5. add diagnostics explaining when each strategy helps or hurts
6. prepare the path for GARCH, MTV-GARCH, and Brazil Stress Transmission Index integration

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
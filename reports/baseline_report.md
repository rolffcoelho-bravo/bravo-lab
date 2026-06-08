# BRAVO Lab Baseline Report

Generated at: **2026-06-08 18:12:02 UTC**

Data window: **2014-01-02 to 2026-06-08**

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

| Asset | Ann. Return | Ann. Volatility | Sharpe | Sortino | Max Drawdown | VaR 95% | CVaR 95% | Obs. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| brazil_equity | 9.92% | 23.14% | 0.525 | 0.686 | -46.93% | -2.21% | -3.28% | 3238 |
| fx_usdbrl | 6.32% | 16.45% | 0.454 | 0.701 | -26.80% | -1.59% | -2.23% | 3238 |
| brazil_external | 2.57% | 33.91% | 0.246 | 0.323 | -66.54% | -3.30% | -4.84% | 3238 |
| global_equity | 13.33% | 16.92% | 0.824 | 0.987 | -33.72% | -1.60% | -2.59% | 3238 |
| vix | 2.09% | 133.48% | 0.623 | 1.273 | -85.66% | -10.53% | -14.21% | 3238 |

## Brazilian Equity Regime Snapshot

Latest classified regime: **stress**

Latest realized volatility: **16.39%**

Latest drawdown: **-15.25%**

## Regime Distribution

| Regime | Observations | Share |
| --- | ---: | ---: |
| stress | 920 | 31.01% |
| extreme_stress | 737 | 24.84% |
| calm | 674 | 22.72% |
| fragile | 334 | 11.26% |
| neutral | 302 | 10.18% |

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
annualized using **12.0 periods per year**.

| Strategy | Ann. Return | Ann. Volatility | Sharpe | Max Drawdown | Best Period | Worst Period | Obs. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| passive_brazil_equity | 9.92% | 22.24% | 0.543 | -37.77% | 21.22% | -35.92% | 151 |
| covered_call | 8.56% | 16.80% | 0.584 | -36.71% | 10.62% | -35.11% | 151 |
| collar | 6.80% | 10.23% | 0.696 | -19.65% | 4.21% | -4.66% | 151 |

## Interpretation

The current regime classifier is intentionally simple. It uses realized
volatility, volatility percentile, and drawdown to classify Brazilian equity
conditions into calm, fragile, stress, and extreme-stress states.

The derivatives overlay layer is also intentionally simple. Its purpose is to
create a transparent baseline before introducing transaction costs, tracking
error discipline, real option-chain data, GARCH, MTV-GARCH, the Brazil Stress
Transmission Index, CCA, wavelets, or ML-based regime classification.

## Generated Files

- `E:\Claude AI\Project_bravo\data\processed\baseline_performance_summary.csv`
- `E:\Claude AI\Project_bravo\data\processed\brazil_equity_regime_table.csv`
- `E:\Claude AI\Project_bravo\data\processed\overlay_return_table.csv`
- `E:\Claude AI\Project_bravo\data\processed\overlay_performance_summary.csv`
- `E:\Claude AI\Project_bravo\reports\baseline_report.md`

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

# BRAVO Lab Baseline Report

Generated at: **2026-06-08 18:00:17 UTC**

Data window: **2014-01-02 to 2026-06-08**

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

| Asset | Ann. Return | Ann. Volatility | Sharpe | Sortino | Max Drawdown | VaR 95% | CVaR 95% | Obs. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| brazil_equity | 9.91% | 23.14% | 0.525 | 0.685 | -46.93% | -2.21% | -3.28% | 3238 |
| fx_usdbrl | 6.33% | 16.46% | 0.455 | 0.702 | -26.80% | -1.59% | -2.23% | 3238 |
| brazil_external | 2.56% | 33.91% | 0.246 | 0.323 | -66.54% | -3.30% | -4.84% | 3238 |
| global_equity | 13.33% | 16.92% | 0.824 | 0.987 | -33.72% | -1.60% | -2.59% | 3238 |
| vix | 2.16% | 133.47% | 0.623 | 1.275 | -85.66% | -10.53% | -14.20% | 3238 |

## Brazilian Equity Regime Snapshot

Latest classified regime: **stress**

Latest realized volatility: **16.38%**

Latest drawdown: **-15.34%**

## Regime Distribution

| Regime | Observations | Share |
| --- | ---: | ---: |
| stress | 920 | 31.01% |
| extreme_stress | 737 | 24.84% |
| calm | 674 | 22.72% |
| fragile | 334 | 11.26% |
| neutral | 302 | 10.18% |

## Interpretation

The current regime classifier is intentionally simple. It uses realized volatility,
volatility percentile, and drawdown to classify Brazilian equity conditions into
calm, fragile, stress, and extreme-stress states.

The objective is to create a transparent baseline before introducing more
advanced layers such as GARCH, MTV-GARCH, the Brazil Stress Transmission Index,
CCA, wavelets, or ML-based regime classification.

## Generated Files

- `E:\Claude AI\Project_bravo\data\processed\baseline_performance_summary.csv`
- `E:\Claude AI\Project_bravo\data\processed\brazil_equity_regime_table.csv`
- `E:\Claude AI\Project_bravo\reports\baseline_report.md`

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

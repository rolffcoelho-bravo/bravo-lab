# BRAVO Lab Market Regime and Overlay Decision Report

**Subtitle:** Brazilian Equity Risk, Volatility Transmission, and Synthetic Protection Logic

Generated at: **2026-06-08 19:05:02 UTC**

Data window: **2014-01-02 to 2026-06-08**

Target report length: **11 to 13 PDF pages**

## 1. Executive Signal

**Current regime:** `stress`

**Latest realized volatility:** 16.40%

**Latest drawdown:** -15.20%

**Decision bias:** Protection bias. The current signal gives more weight to drawdown control than to full upside capture. The strongest drawdown profile is currently `collar`. The strongest risk-adjusted profile is currently `collar`.

ShockBridge Signal: the market is inside a stress transmission zone. Covered calls may monetize volatility, but collars carry stronger portfolio logic while drawdown pressure remains active.

## 2. Report Map

| PDF Page Target | Section | Decision Purpose |
| ---: | --- | --- |
| 1 | Executive Signal | Current regime, decision bias, and portfolio read |
| 2 | Portfolio Question | What the framework is trying to decide |
| 3 | Market State | Cross-market context for Brazil exposure |
| 4 | Data Provenance | Separates real data, derived metrics, synthetic assumptions, and model rules |
| 5 | Regime Diagnosis | Volatility, drawdown, and current regime |
| 6 | Baseline Risk Metrics | Return, risk, Sharpe, drawdown, VaR, CVaR |
| 7 | Synthetic Overlay Results | Passive versus covered call versus collar versus stress-aware overlay |
| 8 | Overlay Decision Matrix | When each strategy is useful or dangerous |
| 9 to 10 | Results SWOT | How to cope with the signal before portfolio action |
| 11 | ShockBridge Transmission Read | How stress moves into the book |
| 12 | What To Watch Next | Confirmation signals and warning signals |
| 13 | Model Limits and Evidence Files | What is proven, what is not, and what comes next |

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

## 5. Data Provenance and Evidence Classification

A robust report must separate observed data from modeled signals.

The market layer uses real public market data downloaded through Yahoo Finance
with `yfinance`. The derivatives layer is synthetic. Covered call and collar
premiums are estimated through the Black-Scholes engine until real B3
listed-option chains are integrated.

This distinction matters. A real price series can support risk measurement. A
synthetic option premium can support research design. It cannot yet support live
execution decisions.

| Layer | Item | Source | Evidence Type | Status |
| --- | --- | --- | --- | --- |
| market_data | brazil_equity | Yahoo Finance through yfinance | real_public_market_price_series | real market proxy |
| market_data | brazil_external | Yahoo Finance through yfinance | real_public_market_price_series | real market proxy |
| market_data | global_equity | Yahoo Finance through yfinance | real_public_market_price_series | real market proxy |
| market_data | fx_usdbrl | Yahoo Finance through yfinance | real_public_market_price_series | real market proxy |
| market_data | vix | Yahoo Finance through yfinance | real_public_market_price_series | real market proxy |
| derived_metric | realized_volatility | BRAVO Lab calculation | model_derived | derived from real market data |
| derived_metric | drawdown | BRAVO Lab calculation | model_derived | derived from real market data |
| regime_signal | baseline_regime_classifier | BRAVO Lab rule-based classifier | model_generated_signal | decision signal, not observed market data |
| synthetic_derivatives | covered_call_overlay | BRAVO Lab synthetic option engine | synthetic_research_assumption | not real B3 option-chain evidence |
| synthetic_derivatives | collar_overlay | BRAVO Lab synthetic option engine | synthetic_research_assumption | not real B3 option-chain evidence |
| strategy_logic | stress_aware_overlay | BRAVO Lab switching rule | model_generated_strategy_rule | research rule requiring validation |

## 6. Regime Diagnosis

The current Brazilian equity signal sits in `stress`.

That matters because the same overlay can behave well in one regime and poorly
in another. A covered call can create useful income in a range-bound market, but
it can also sell the recovery too cheaply. A collar can protect the book during
stress, but it can also become expensive insurance if drawdown risk fades.

The regime classifier uses realized volatility, volatility percentile, and
drawdown. It is simple by design. The point is to create an auditable baseline
before adding GARCH, MTV-GARCH, stress transmission indexes, wavelets, CCA, or
machine learning.

### Regime Snapshot

Latest classified regime: **stress**

Latest realized volatility: **16.40%**

Latest drawdown: **-15.20%**

### Regime Distribution

| Regime | Observations | Share |
| --- | ---: | ---: |
| stress | 920 | 31.01% |
| extreme_stress | 737 | 24.84% |
| calm | 674 | 22.72% |
| fragile | 334 | 11.26% |
| neutral | 302 | 10.18% |

## 7. Baseline Risk Metrics

The table below gives the first risk layer across the monitored assets. It is
not a final allocation model. It is the risk map used to decide whether the
overlay discussion is taking place in a calm, fragile, or stressed environment.

| Asset | Ann. Return | Ann. Volatility | Sharpe | Sortino | Max Drawdown | VaR 95% | CVaR 95% | Obs. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| brazil_equity | 9.92% | 23.14% | 0.525 | 0.686 | -46.93% | -2.21% | -3.28% | 3238 |
| fx_usdbrl | 6.32% | 16.45% | 0.454 | 0.701 | -26.80% | -1.59% | -2.23% | 3238 |
| brazil_external | 2.57% | 33.91% | 0.246 | 0.323 | -66.54% | -3.30% | -4.84% | 3238 |
| global_equity | 13.32% | 16.92% | 0.824 | 0.986 | -33.72% | -1.60% | -2.59% | 3238 |
| vix | 2.12% | 133.47% | 0.623 | 1.274 | -85.66% | -10.53% | -14.21% | 3238 |

## 8. Synthetic Overlay Results

The first overlay engine compares four exposures:

- passive Brazilian equity exposure
- synthetic covered call overlay
- synthetic protective collar overlay
- stress-aware overlay switching

The engine uses a 21-trading-day rebalance approximation, synthetic
Black-Scholes option premiums, and a transaction-cost assumption of
**5.0 basis points per option leg**.

The stress-aware overlay maps regimes into actions: passive exposure in calm
conditions, covered call income in fragile conditions, and collar protection in
stress or extreme-stress conditions. It does not claim live tradability. It is a
controlled research baseline before adding real B3 option chains, taxes,
liquidity, and execution constraints.

Returns in this section are approximately monthly strategy-period returns,
annualized using **12.0 periods per year**.

| Strategy | Ann. Return | Ann. Volatility | Sharpe | Max Drawdown | Best Period | Worst Period | Obs. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| passive_brazil_equity | 9.93% | 22.24% | 0.543 | -37.77% | 21.22% | -35.92% | 151 |
| covered_call | 7.92% | 16.80% | 0.549 | -36.79% | 10.57% | -35.16% | 151 |
| collar | 5.54% | 10.23% | 0.579 | -21.49% | 4.11% | -4.76% | 151 |
| stress_aware_overlay | 6.79% | 13.62% | 0.552 | -23.01% | 10.58% | -14.33% | 151 |

## 9. Overlay Decision Matrix

| Strategy | Best Use | Main Risk | Portfolio Reading |
| --- | --- | --- | --- |
| Passive Brazilian Equity | Clean trend, calm regime, strong rebound | Full downside exposure | Use when upside participation matters more than protection |
| Covered Call | Fragile regime, elevated volatility, income objective | Upside is capped | Use when premium harvesting matters more than full upside capture |
| Collar | Stress regime, drawdown pressure, capital preservation | Protection cost and capped upside | Use when left-tail control matters more than return maximization |
| Stress-Aware Overlay | Regime-dependent switching | Model risk and signal timing | Uses passive in calm regimes, covered calls in fragile regimes, and collars in stress regimes |

## 10. Strategy Trade-Off

**Best annualized return:** `passive_brazil_equity`

**Best drawdown profile:** `collar`

**Best Sharpe profile:** `collar`

**Weakest drawdown profile:** `passive_brazil_equity`

The decision is not to chase the highest return. The decision is to match the
overlay to the regime.

Passive equity keeps the cleanest upside but carries the full left tail. Covered
calls convert part of upside into premium income, which can help in sideways or
moderately volatile markets. Collars give the book a defined protection logic,
but their cost and upside cap must be justified by the current risk state.

## 11. Results SWOT

How to cope with the signal before turning it into a portfolio action.

This SWOT does not evaluate BRAVO Lab as a business project. It evaluates the current result as a portfolio decision signal.

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

The main threat is clean-model illusion. A strategy can look strong before costs, spreads, liquidity, and stress subperiods. The next version must attack that weakness directly.

## 12. ShockBridge Transmission Read

Brazilian equity does not trade in isolation. The book can be hit through local
rates, fiscal repricing, FX pressure, global volatility, commodity shocks, and
external risk appetite.

This first version does not model every channel. It builds the base layer that
future ShockBridge modules can extend into a formal Brazil Stress Transmission
Index.

The key insight is simple: volatility is not only a number. It is a carrier of
stress. When volatility rises with drawdown, the book is not just moving. It is
absorbing transmission.

## 13. What To Watch Next

Watch whether drawdown stabilizes while realized volatility falls. If that does not happen, protection remains more valuable than income. If volatility falls without price repair, the market may be hiding fragility under calmer surface data.

The next model version should not simply add complexity. It should improve the
decision. The immediate test is whether transaction costs, tracking error, and
stress subperiod performance confirm or weaken the current overlay ranking.

## 14. What Would Break This View

This baseline view should be challenged if one of the following happens:

1. The regime classifier changes but overlay results do not respond.
2. Synthetic option premiums diverge too far from real B3 listed-option behavior.
3. Transaction costs erase the apparent benefit of the overlay.
4. The collar improves drawdown but destroys too much participation.
5. The covered call improves income but systematically sells the strongest rebounds.
6. The model performs well in the full sample but fails in stress subperiods.

## 15. Model Limits and Governance

This report is intentionally clear about what it does not prove.

- Yahoo Finance data is used as the baseline public-data source.
- No real B3 option-chain data is used yet.
- Option premiums are synthetic Black-Scholes approximations.
- Transaction costs, taxes, spreads, and liquidity constraints are not included yet.
- GARCH and MTV-GARCH are not yet active in this report.
- The regime classifier is transparent but not final.
- This is research infrastructure, not investment advice.

## 16. Generated Evidence Files

- `E:\Claude AI\Project_bravo\data\processed\baseline_performance_summary.csv`
- `E:\Claude AI\Project_bravo\data\processed\brazil_equity_regime_table.csv`
- `E:\Claude AI\Project_bravo\data\processed\overlay_return_table.csv`
- `E:\Claude AI\Project_bravo\data\processed\overlay_performance_summary.csv`
- `E:\Claude AI\Project_bravo\data\processed\data_provenance_table.csv`
- `E:\Claude AI\Project_bravo\reports\baseline_report.md`

## 17. Next Upgrade

The next upgrade should turn this from a static overlay comparison into a
stress-aware decision engine:

1. calculate tracking error versus passive Brazilian equity
2. isolate stress subperiod performance
3. add diagnostics explaining when each strategy helps or hurts
4. test alternative transaction-cost levels
5. prepare the path for GARCH, MTV-GARCH, and Brazil Stress Transmission Index integration

## Research Use Only

This report is generated by BRAVO Lab for reproducible research and portfolio
discussion. It is not a trading recommendation, not a solicitation, and not a
production investment model.

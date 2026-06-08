# BRAVO Lab Market Regime and Overlay Decision Report

**Subtitle:** Brazilian Equity Risk, Volatility Transmission, and Synthetic Protection Logic

Generated at: **2026-06-08 19:48:04 UTC**

Data window: **2014-01-02 to 2026-06-08**

Target report length: **16 to 18 PDF pages**

## 1. Executive Signal

**Current regime:** `stress`

**Latest realized volatility:** 16.41%

**Latest drawdown:** -15.19%

**Decision bias:** Protection bias. The current signal gives more weight to drawdown control than to full upside capture. The strongest drawdown profile is currently `collar`. The strongest risk-adjusted profile is currently `collar`.

**Best information ratio versus passive:** `covered_call`

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
| 8 | Active Risk Diagnostics | Tracks active return, tracking error, hit rate, and information ratio |
| 9 | Regime and Stress Diagnostics | Tests whether the overlay helps when market pressure rises |
| 10 | Strategy Help-Hurt Diagnostics | Explains when each overlay adds value or creates drag |
| 11 | Implementation Drag Diagnostics | Separates gross signal, cost drag, and net overlay effect |
| 12 | Overlay Decision Matrix | When each strategy is useful or dangerous |
| 13 to 14 | Results SWOT | How to cope with the signal before portfolio action |
| 13 | ShockBridge Transmission Read | How stress moves into the book |
| 14 | What To Watch Next | Confirmation signals and warning signals |
| 15 | Model Limits and Evidence Files | What is proven, what is not, and what comes next |

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

Latest realized volatility: **16.41%**

Latest drawdown: **-15.19%**

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
| brazil_external | 2.56% | 33.91% | 0.246 | 0.323 | -66.54% | -3.30% | -4.84% | 3238 |
| global_equity | 13.31% | 16.92% | 0.823 | 0.986 | -33.72% | -1.60% | -2.59% | 3238 |
| vix | 2.20% | 133.47% | 0.624 | 1.275 | -85.66% | -10.53% | -14.20% | 3238 |

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

## 9. Active Risk Diagnostics

Absolute return is not enough. A portfolio desk also needs to know whether the
overlay earns enough to justify its deviation from passive Brazilian equity.

Tracking error measures how far the overlay moves away from passive exposure.
The information ratio tests whether that active deviation is rewarded. Hit rate
shows how often the overlay beats passive. Downside hit rate is stricter. It
asks whether the overlay helps when passive exposure is already losing money.

| Strategy | Ann. Active Return | Tracking Error | Information Ratio | Hit Rate | Downside Hit Rate | Worst Active Period | Obs. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| covered_call | -2.87% | 10.33% | -0.278 | 74.83% | 100.00% | -16.46% | 151 |
| collar | -6.16% | 14.82% | -0.416 | 69.54% | 100.00% | -17.62% | 151 |
| stress_aware_overlay | -4.57% | 13.62% | -0.335 | 44.37% | 64.18% | -17.62% | 151 |

## 10. Regime and Stress-Window Diagnostics

Full-sample metrics can hide the real question. A strategy that looks strong in
normal conditions may fail when the benchmark is under pressure.

This section tests the overlay behavior by regime and during stress windows. The
goal is to identify whether the strategy helps when protection, income discipline,
and active-risk control matter most.

### Regime-Level Performance

| Regime | Strategy | Avg. Period Return | Median Period Return | Best Period | Worst Period | Positive Hit Rate | Obs. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| calm | passive_brazil_equity | 3.81% | 3.29% | 12.50% | -4.07% | 76.67% | 30 |
| calm | covered_call | 2.36% | 3.45% | 4.78% | -3.45% | 80.00% | 30 |
| calm | collar | 1.82% | 3.19% | 3.61% | -3.76% | 76.67% | 30 |
| calm | stress_aware_overlay | 2.92% | 3.13% | 10.58% | -4.07% | 80.00% | 30 |
| extreme_stress | passive_brazil_equity | -1.04% | -1.04% | 21.22% | -35.92% | 38.24% | 34 |
| extreme_stress | covered_call | -0.92% | 0.18% | 10.57% | -35.16% | 52.94% | 34 |
| extreme_stress | collar | -0.43% | -0.63% | 4.11% | -4.65% | 47.06% | 34 |
| extreme_stress | stress_aware_overlay | -0.77% | -0.63% | 4.11% | -14.33% | 47.06% | 34 |
| fragile | passive_brazil_equity | 0.94% | 0.49% | 10.54% | -6.64% | 57.14% | 21 |
| fragile | covered_call | 0.83% | 1.36% | 4.48% | -5.13% | 61.90% | 21 |
| fragile | collar | 0.39% | 0.90% | 3.55% | -4.51% | 57.14% | 21 |
| fragile | stress_aware_overlay | 0.77% | 0.49% | 10.54% | -5.27% | 57.14% | 21 |
| neutral | passive_brazil_equity | 1.11% | 0.66% | 12.47% | -8.34% | 57.14% | 21 |
| neutral | covered_call | 0.72% | 1.62% | 5.33% | -7.38% | 61.90% | 21 |
| neutral | collar | 0.50% | 1.11% | 3.69% | -4.61% | 57.14% | 21 |
| neutral | stress_aware_overlay | 0.42% | 0.75% | 7.68% | -8.34% | 57.14% | 21 |
| stress | passive_brazil_equity | 0.67% | 0.19% | 17.55% | -8.72% | 51.11% | 45 |
| stress | covered_call | 0.98% | 1.59% | 7.35% | -7.58% | 62.22% | 45 |
| stress | collar | 0.35% | 0.72% | 3.90% | -4.76% | 53.33% | 45 |
| stress | stress_aware_overlay | 0.18% | 0.72% | 3.90% | -7.58% | 53.33% | 45 |

### Stress-Window Summary

| Strategy | Avg. Stress Return | Median Stress Return | Worst Stress Return | Best Stress Return | Hit Rate vs Passive | Downside Protection Rate | Obs. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| passive_brazil_equity | -0.07% | -0.37% | -35.92% | 21.22% | NA | NA | 79 |
| covered_call | 0.16% | 0.91% | -35.16% | 10.57% | 83.54% | 100.00% | 79 |
| collar | 0.02% | 0.17% | -4.76% | 4.11% | 75.95% | 100.00% | 79 |
| stress_aware_overlay | -0.23% | 0.17% | -14.33% | 4.11% | 62.03% | 78.57% | 79 |

### Stress-Window Interpretation

Stress-window read: `collar` showed the strongest worst-period protection during stress windows, while `covered_call` showed the strongest average stress-period return. The portfolio question is whether the protection benefit is large enough to justify the active risk and implementation complexity.

## 11. Strategy Help-Hurt Diagnostics

The help-hurt diagnostic explains the trade-off behind each overlay. A strategy
can protect the downside and still hurt the portfolio if it gives away too much
rebound. It can also improve income while failing to protect the book when the
benchmark is already falling.

This section separates the periods where each overlay adds active value from the
periods where it creates drag versus passive Brazilian equity.

| Strategy | Avg. Active Return | Active When Passive Up | Active When Passive Down | Hit Rate | Missed Upside Rate | Downside Protection Rate | Best Active Period | Worst Active Period | Primary Help | Primary Hurt | Obs. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| covered_call | -0.24% | -1.32% | 1.08% | 74.83% | 45.78% | 100.00% | 7.34% | -16.46% | downside_protection | missed_upside | 151 |
| collar | -0.51% | -2.23% | 1.60% | 69.54% | 55.42% | 100.00% | 31.28% | -17.62% | downside_protection | missed_upside | 151 |
| stress_aware_overlay | -0.38% | -1.61% | 1.13% | 44.37% | 38.55% | 64.18% | 31.28% | -17.62% | downside_protection | missed_upside | 151 |

### Help-Hurt Interpretation

Help-hurt read: `covered_call` currently shows the strongest downside protection behavior versus passive exposure. `collar` shows the highest missed-upside risk when passive Brazilian equity is positive. This is the central overlay trade-off: the portfolio can reduce left-tail pain, but protection and income strategies can also give away part of the rebound.

## 12. Implementation Drag Diagnostics

The implementation-drag diagnostic separates the gross overlay signal from the
net result after transaction costs. This matters because an overlay can look
useful before costs and still fail after realistic rebalancing drag.

The diagnostic does not yet decompose every option leg into premium income,
payoff effect, and moneyness attribution. It is the intermediate institutional
layer showing whether the overlay signal survives implementation.

| Strategy | Gross Active | Implementation Drag | Net Active | Total Drag | Drag / Gross Signal | Cost Survival | Active When Passive Up | Active When Passive Down | Best Net Active | Worst Net Active | Obs. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| covered_call | -0.19% | -0.05% | -0.24% | -7.55% | 0.265 | 1.265 | -1.32% | 1.08% | 7.34% | -16.46% | 151 |
| collar | -0.41% | -0.10% | -0.51% | -15.10% | 0.242 | 1.242 | -2.23% | 1.60% | 31.28% | -17.62% | 151 |
| stress_aware_overlay | -0.32% | -0.06% | -0.38% | -8.85% | 0.182 | 1.182 | -1.61% | 1.13% | 31.28% | -17.62% | 151 |

### Implementation Interpretation

Implementation read: `covered_call` currently shows the strongest average net active return after transaction costs. `covered_call` is the most cost-sensitive overlay by drag-to-gross signal ratio. This matters because an overlay that looks useful before costs can become weak once turnover, option-leg execution, and rebalancing drag are included.

## 13. Overlay Decision Matrix

| Strategy | Best Use | Main Risk | Portfolio Reading |
| --- | --- | --- | --- |
| Passive Brazilian Equity | Clean trend, calm regime, strong rebound | Full downside exposure | Use when upside participation matters more than protection |
| Covered Call | Fragile regime, elevated volatility, income objective | Upside is capped | Use when premium harvesting matters more than full upside capture |
| Collar | Stress regime, drawdown pressure, capital preservation | Protection cost and capped upside | Use when left-tail control matters more than return maximization |
| Stress-Aware Overlay | Regime-dependent switching | Model risk and signal timing | Uses passive in calm regimes, covered calls in fragile regimes, and collars in stress regimes |

## 14. Strategy Trade-Off

**Best annualized return:** `passive_brazil_equity`

**Best drawdown profile:** `collar`

**Best Sharpe profile:** `collar`

**Best information ratio versus passive:** `covered_call`

**Weakest drawdown profile:** `passive_brazil_equity`

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

This SWOT does not evaluate BRAVO Lab as a business project. It evaluates the current result as a portfolio decision signal.

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

The main threat is clean-model illusion. A strategy can look strong before costs, spreads, liquidity, and stress subperiods. The next version must attack that weakness directly.

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

Watch whether drawdown stabilizes while realized volatility falls. If that does not happen, protection remains more valuable than income. If volatility falls without price repair, the market may be hiding fragility under calmer surface data.

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

- `E:\Claude AI\Project_bravo\data\processed\baseline_performance_summary.csv`
- `E:\Claude AI\Project_bravo\data\processed\brazil_equity_regime_table.csv`
- `E:\Claude AI\Project_bravo\data\processed\overlay_return_table.csv`
- `E:\Claude AI\Project_bravo\data\processed\overlay_performance_summary.csv`
- `E:\Claude AI\Project_bravo\data\processed\data_provenance_table.csv`
- `E:\Claude AI\Project_bravo\data\processed\active_risk_summary.csv`
- `E:\Claude AI\Project_bravo\data\processed\regime_performance_summary.csv`
- `E:\Claude AI\Project_bravo\data\processed\stress_window_summary.csv`
- `E:\Claude AI\Project_bravo\data\processed\strategy_help_hurt_summary.csv`
- `E:\Claude AI\Project_bravo\data\processed\implementation_drag_summary.csv`
- `E:\Claude AI\Project_bravo\reports\baseline_report.md`

## 21. Next Upgrade

The next upgrade should turn this from a stress-window decision memo into a
more realistic implementation framework:

1. test alternative transaction-cost levels
2. calculate active risk by regime depth and drawdown severity
3. decompose option overlays into premium income, payoff effect, and moneyness attribution
4. integrate real B3 option-chain data when available
5. prepare the path for GARCH, MTV-GARCH, and Brazil Stress Transmission Index integration

## Research Use Only

This report is generated by BRAVO Lab for reproducible research and portfolio
discussion. It is not a trading recommendation, not a solicitation, and not a
production investment model.

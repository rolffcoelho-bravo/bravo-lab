# BRAVO Lab Front-Office Executive Memo

**Purpose:** portfolio-governance decision support for Brazilian risk, volatility transmission, and overlay policy selection.

### Decision read

BRAVO Lab currently reads Brazilian risk through a BSTI score of **31.27**, classified as **Fragile**, with **Fx Pressure** as the dominant pressure channel. The current BSTI policy action is **Covered Call**.

The model is prioritizing income capture. The committee should check whether the upside sold is acceptable under the current stress state.

### Portfolio action snapshot

| Item | Current read |
| --- | --- |
| Current BSTI score | 31.27 |
| Current BSTI regime | Fragile |
| Dominant pressure channel | Fx Pressure |
| Current policy action | Covered Call |
| Dominant historical policy choice | Passive Brazil Equity (60.93%) |
| BSTI policy annualized active return | 5.54% |
| BSTI policy tracking error | 10.18% |
| BSTI policy information ratio | 0.54 |
| BSTI policy max drawdown | -25.01% |

### Evidence stack

| Question | Evidence read |
| --- | --- |
| Which strategy had the best information ratio? | Bsti Policy Overlay |
| Which strategy had the best drawdown profile? | Collar |
| Which strategy had the highest annualized return? | Bsti Policy Overlay |
| How persistent are warning states? | Average warning duration: 1.88 observations |
| How persistent are stress states? | Average stress duration: 1.71 observations |
| How often do warnings escalate? | Warning-to-stress escalation rate: 24.17% |
| Which BSTI calibration is strongest? | Balanced, 63d horizon, threshold 10.00, governance score 0.50 |

### Risk committee agenda

1. Confirm whether the current BSTI state is persistent or only a temporary pressure print.
2. Check whether the implied policy action matches the committee's drawdown tolerance.
3. Compare the BSTI policy overlay against passive equity, covered calls, collars, and the local stress-aware overlay.
4. Review whether the selected action is justified after transaction costs, liquidity, taxes, and implementation constraints.
5. Decide whether the stress state requires monitoring, hedge discussion, or actual overlay activation.

### Implementation warning

This memo is a decision-support layer, not an investment recommendation. The evidence is generated from public market data, synthetic option-premium logic, transparent stress classification, and reproducible CSV outputs. Real B3 option-chain data, liquidity filters, tax effects, and portfolio mandate constraints must be added before production use.

## Visual Evidence

See `reports/figures/` for the executive dashboard, drawdown map, BSTI signal, policy-selection mix, risk-return map, transition matrix, and calibration scorecard.

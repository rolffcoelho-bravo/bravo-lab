# Methodology

## Research objective

BRAVO Lab studies whether Brazilian equity derivatives overlays can be improved by using volatility regimes, contagion signals, transaction-cost-aware backtesting, and advanced financial-econometric risk models.

The practical portfolio question is:

**When should a Brazilian equity overlay generate income, and when should it shift toward downside protection?**

## Portfolio problem

A covered call strategy can monetize volatility and generate carry, but it may cap upside during recovery periods. A collar can reduce downside exposure, but it may reduce participation and introduce option-cost drag.

The project tests whether risk-regime information can improve the decision between:

* passive equity exposure
* covered call overlay
* collar overlay
* stress-aware dynamic overlay

## Data layer

The planned data layer should support:

* BOVA11 or IBOV-style Brazilian equity exposure
* EWZ as an external Brazil proxy
* SPY as a global equity benchmark
* USD/BRL
* VIX
* Brazilian interest-rate proxies such as CDI / Selic
* optional commodity and sector proxies

## Data-source assumptions

Initial versions may use freely available data sources such as Yahoo Finance, public central-bank data, and documented proxies.

Every dataset should be documented with:

* source
* ticker or series identifier
* frequency
* currency
* start and end date
* cleaning rules
* known limitations

## Cleaning rules

The data pipeline should define:

* date alignment
* missing-value treatment
* duplicate removal
* return calculation
* calendar mismatch handling
* outlier inspection
* data quality flags

## Return calculation

Returns should be calculated consistently, preferably using log returns for modeling layers and simple returns for portfolio performance accounting where appropriate.

The methodology should clearly separate:

* model returns
* strategy returns
* benchmark returns
* cumulative performance series

## Feature engineering

The baseline feature layer should include:

* realized volatility
* rolling drawdown
* downside deviation
* rolling correlation
* return asymmetry
* FX stress
* global risk proxy movement
* volatility percentile
* market-regime classification inputs

## Volatility regime engine

The initial regime engine should classify market states such as:

* calm
* fragile
* stress
* extreme stress

A simple first version can rely on realized volatility, drawdown, and volatility percentiles. More advanced versions should incorporate GARCH and dynamic covariance estimates.

## MTV-GARCH role

Multivariate Time-Varying GARCH is intended to estimate how Brazilian equity risk changes jointly with global stress variables.

The role of the MTV-GARCH layer is not decorative. It should support portfolio decisions by identifying periods when conditional volatility and cross-market dependence increase together.

Potential output:

* conditional volatility estimate
* dynamic covariance estimate
* dynamic correlation estimate
* stress contribution to the Brazil Stress Transmission Index

## Fallback if MTV-GARCH is not fully implemented

If full MTV-GARCH implementation is not available in the first version, the project should use a transparent fallback such as:

* univariate GARCH per asset
* rolling covariance
* rolling correlation
* DCC-style approximation
* volatility-adjusted stress score

The fallback must be clearly labeled.

## Brazil Stress Transmission Index

The Brazil Stress Transmission Index, or BR-STI, is planned as a composite score from 0 to 100.

Possible inputs:

* Brazilian equity realized volatility
* drawdown intensity
* USD/BRL pressure
* VIX percentile
* EWZ versus SPY divergence
* rolling Brazil-global correlation
* conditional covariance from the GARCH layer
* optional wavelet or CCA stress factor in later versions

Suggested interpretation:

|  Score | Regime         |
| -----: | -------------- |
|   0-30 | Calm           |
|  30-55 | Fragile        |
|  55-75 | Stress         |
| 75-100 | Extreme stress |

## Contagion signal logic

A contagion signal should capture whether Brazilian assets are moving from idiosyncratic volatility into broader stress transmission.

Possible indicators:

* rising conditional correlation
* FX stress combined with equity drawdown
* EWZ underperformance versus SPY
* volatility clustering
* synchronized downside moves
* high-dimensional stress compression in future versions

## High-dimensional research extension

Future extensions may include:

* B3 sector blocks
* IBrX 100 constituents
* Ridge CCA / Sparse CCA
* wavelet decomposition
* network contagion maps
* ML regime classification

The high-dimensional layer should only be added after the baseline pipeline is reproducible.

## Options pricing assumptions

If real B3 option-chain data is not available, the first implementation may use synthetic option premiums.

Synthetic premiums should be based on:

* underlying price
* strike
* time to maturity
* risk-free proxy
* volatility estimate
* option-pricing assumptions

This limitation must be visible in the report.

## Covered call strategy logic

Planned baseline rules:

* hold Brazilian equity exposure
* sell an out-of-the-money call
* rebalance monthly
* estimate premium using documented assumptions
* deduct transaction costs
* compare against passive exposure

## Collar strategy logic

Planned baseline rules:

* hold Brazilian equity exposure
* sell an out-of-the-money call
* buy an out-of-the-money put
* apply during elevated stress regimes
* deduct premium and transaction costs
* compare downside capture and tracking error

## Stress-aware strategy switching

Example rule structure:

```text
calm regime       → covered call
fragile regime    → passive or light overwrite
stress regime     → collar
extreme stress    → stronger protection or defensive allocation
```

The final implementation should test whether switching improves risk-adjusted performance after costs.

## Backtesting assumptions

The backtest should document:

* rebalance frequency
* option maturity proxy
* strike selection
* execution assumptions
* transaction costs
* slippage assumptions
* benchmark
* no-look-ahead design
* survivorship limitations

## Transaction costs

Transaction costs should be explicit and stress-tested.

The report should show:

* gross performance
* net performance
* cost drag
* turnover
* sensitivity to cost assumptions

## Tracking error

Tracking error is important because a derivatives overlay may reduce drawdowns while also moving away from the benchmark.

The pipeline should report:

* tracking error
* information ratio
* upside capture
* downside capture
* strategy-beta behavior

## Performance metrics

Planned metrics:

* total return
* annualized return
* annualized volatility
* Sharpe ratio
* Sortino ratio
* maximum drawdown
* Calmar ratio
* tracking error
* information ratio
* VaR
* CVaR
* turnover
* cost drag

## Validation logic

The validation layer should include:

* in-sample / out-of-sample separation
* walk-forward testing
* stress-window analysis
* parameter sensitivity
* benchmark comparison
* robustness checks

## Walk-forward testing

A possible structure:

* calibration window
* validation window
* out-of-sample test window

The objective is to reduce overfitting and show whether regime logic survives outside the calibration period.

## Sensitivity analysis

The strategy should test:

* call strike distance
* put strike distance
* rebalance frequency
* transaction-cost levels
* volatility input choice
* stress threshold
* GARCH versus realized volatility signal

## Report-generation logic

The final report should be automatically generated from pipeline outputs.

Planned sections:

* executive summary
* data quality
* market regime analysis
* strategy comparison
* risk metrics
* stress-window performance
* decision matrix
* limitations
* next steps

## Limitations

Important limitations include:

* proxy data may not match tradable instruments perfectly
* synthetic option pricing is not the same as real option-chain execution
* transaction costs are estimates
* regime thresholds may be unstable
* GARCH models are sensitive to specification
* high-dimensional extensions require careful validation

## Production extension roadmap

In a production asset-management environment, the project could be extended with:

* real B3 option-chain data
* internal execution-cost estimates
* Databricks or cloud pipeline orchestration
* scheduled report generation
* dashboard monitoring
* risk committee export
* model governance documentation
* automated data-quality alerts

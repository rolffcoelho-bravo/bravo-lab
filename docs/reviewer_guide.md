# Reviewer Guide

This guide is written for a technical reviewer, portfolio researcher, or asset-management professional inspecting BRAVO Lab.

## What to read first

1. `README.md` for the project overview.
2. `docs/methodology.md` for the research design.
3. `reports/nu_asset_application_note.md` for the role-relevance explanation.
4. `src/bravo/` for the planned implementation structure.

## What this repository is trying to prove

The repository is designed to show that advanced financial-econometric thinking can be translated into a practical Python research pipeline.

The focus is not only on models. The focus is the full chain:

```text
data → features → regimes → strategy rules → backtest → validation → report
```

A reviewer should evaluate whether the project shows:

* Brazilian market awareness
* derivatives and overlay logic
* volatility and stress-regime thinking
* reproducible research discipline
* honest documentation of limitations
* a credible path toward decision-grade reporting

## What to run first

At the current documentation phase:

```bash
make smoke-test
```

This command is intentionally lightweight. Full strategy execution will be added in later phases.

## How to generate the final report

The final automated report command is planned as:

```bash
make report
```

In the current phase, this command acts as a placeholder and explains the intended report output.

The planned report should eventually include:

* data quality summary
* realized volatility and GARCH diagnostics
* dynamic covariance / MTV-GARCH risk layer
* Brazil Stress Transmission Index
* strategy comparison tables
* transaction-cost impact
* tracking error
* drawdown analysis
* stress-window performance
* final decision matrix
* limitations and caveats

## How to judge code quality

When implementation begins, evaluate:

* modular functions in `src/bravo`
* separation between data, features, strategies, metrics, validation, and reporting
* explicit assumptions
* no look-ahead bias
* reproducibility
* readable function names
* tests for core calculations
* simple command-line workflow

## How to judge research quality

The project should be judged by whether it connects methods to portfolio decisions.

Good signs:

* models are tied to strategy behavior
* transaction costs are included
* benchmark comparison is visible
* tracking error is measured
* stress periods are separated from normal periods
* limitations are explicit
* the final report avoids exaggerated claims

## Key assumptions to inspect

* use of BOVA11 / IBOV proxies
* synthetic option-premium assumptions
* volatility input selection
* transaction-cost assumptions
* stress-regime thresholds
* treatment of missing data
* benchmark definition
* out-of-sample validation design

## Current limitations

* full data pipeline is not yet implemented
* options data may initially use synthetic pricing assumptions
* MTV-GARCH layer is planned and may require fallback logic
* high-dimensional CCA, wavelets, ML, and networks are future extensions
* no performance results should be assumed until backtests are implemented

## Reviewer checklist

* [ ] Is the investment problem clear?
* [ ] Are assumptions visible?
* [ ] Is the repository structure professional?
* [ ] Is the project honest about implementation status?
* [ ] Is there a credible path from data to report?
* [ ] Does the methodology connect models to portfolio decisions?
* [ ] Does the project avoid fake performance claims?
* [ ] Would the pipeline be extendable in a real portfolio research environment?

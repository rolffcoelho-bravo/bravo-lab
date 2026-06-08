# BRAVO Lab

**Brazilian Risk, Allocation, Volatility & Options Lab**

BRAVO Lab is a Python portfolio research prototype for Brazilian volatility-aware derivatives overlays, risk-regime analysis, contagion signals, and decision-grade portfolio reporting.

The project is designed to test whether systematic Brazilian equity overlays, especially covered calls, collars, and stress-aware downside protection structures, can be improved by combining volatility regimes, transaction-cost-aware backtesting, dynamic risk models, and financial-econometric stress indicators.

This repository is not a trading recommendation. It is a research infrastructure prototype built to show how Brazilian market knowledge, derivatives logic, financial econometrics, and automation can be transformed into a repeatable portfolio research pipeline.

## Why this project matters

Brazilian assets often move through regimes shaped by local interest rates, FX pressure, global risk appetite, commodity shocks, political stress, liquidity conditions, and external contagion channels.

A derivatives overlay that works in calm markets may behave very differently during stress. BRAVO Lab is built around one practical question:

**Can volatility and contagion signals improve the timing and structure of derivatives overlays in Brazilian equity exposure?**

The long-term goal is to generate a decision-grade report that can support real portfolio discussion, including:

* data quality summary
* market regime summary
* volatility analysis
* GARCH / MTV-GARCH risk layer
* Brazil Stress Transmission Index
* covered call and collar strategy evaluation
* passive benchmark comparison
* transaction-cost impact
* tracking error
* drawdown and stress-window analysis
* limitations and implementation caveats
* final decision matrix

## Strategy universe

The planned research pipeline compares four strategy families:

1. **Passive Brazilian equity exposure**
   Benchmark exposure using BOVA11 / IBOV-style proxies.

2. **Systematic covered call overlay**
   Equity exposure with recurring call overwrite logic.

3. **Protective collar overlay**
   Equity exposure combined with sold calls and purchased downside protection.

4. **Stress-aware dynamic overlay**
   Strategy behavior changes according to volatility, drawdown, contagion, and stress-regime signals.

## Model architecture

The project follows a layered methodology:

1. Baseline realized-volatility features
2. Rolling drawdown and downside-risk indicators
3. GARCH volatility layer
4. Multivariate Time-Varying GARCH or DCC-style dynamic covariance fallback
5. Brazil Stress Transmission Index
6. Future CCA / Ridge CCA stress-compression layer
7. Future wavelet stress decomposition
8. Future ML regime-classification robustness layer
9. Future high-dimensional network contagion extension

## Repository structure

```text
bravo-lab/
├── app/
├── data/
│   ├── raw/
│   └── processed/
├── docs/
│   ├── methodology.md
│   └── reviewer_guide.md
├── notebooks/
├── reports/
│   ├── figures/
│   └── nu_asset_application_note.md
├── src/
│   └── bravo/
├── Makefile
├── README.md
└── requirements.txt
```

## Quickstart

Phase 1 is documentation and repository structure. Full implementation is planned in the next phase.

```bash
pip install -r requirements.txt
make smoke-test
make report
```

At this stage, the Makefile commands are intentionally conservative and do not claim completed strategy results.

## Current implementation status

| Component                            | Status  |
| ------------------------------------ | ------- |
| Repository structure                 | Created |
| Reviewer documentation               | Phase 1 |
| Data pipeline                        | Planned |
| Volatility regime engine             | Planned |
| MTV-GARCH / dynamic covariance layer | Planned |
| Brazil Stress Transmission Index     | Planned |
| Options strategy backtests           | Planned |
| Automated decision-grade report      | Planned |

## Roadmap

### Phase 1: Reviewer-facing documentation

Create a clear professional layer explaining the investment problem, methodology, assumptions, and reviewer workflow.

### Phase 2: Data and baseline metrics

Build reproducible data ingestion, return construction, realized volatility, drawdown metrics, and benchmark analysis.

### Phase 3: Options overlay backtests

Implement synthetic covered call and collar logic with transaction costs, tracking error, and stress-window analysis.

### Phase 4: Advanced risk engine

Add GARCH, MTV-GARCH or DCC-style fallback logic, and the Brazil Stress Transmission Index.

### Phase 5: Decision-grade reporting

Generate an automated report suitable for investment, portfolio solutions, or risk-committee review.

## Reviewer note

This repository is intentionally transparent about what is implemented and what is planned. It is designed to demonstrate research architecture, market understanding, reproducibility discipline, and the ability to convert advanced financial-econometric ideas into usable portfolio research infrastructure.

## Disclaimer

This project is for research, education, and portfolio infrastructure demonstration only. It does not provide investment advice, trading recommendations, or performance guarantees.

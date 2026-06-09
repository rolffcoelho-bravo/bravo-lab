# BRAVO Lab Review Guide

BRAVO Lab is an employer-neutral research and portfolio-risk project. It was not built for one company, one recruiter, or one application process.

## What the reviewer should open first

1. `reports/BRAVO_Lab_Executive_Report_v0.1.2.pdf`
2. `reports/front_office_memo.md`
3. `reports/baseline_report.md`
4. `reports/figures/`
5. `scripts/generate_institutional_pdf.py`
6. `src/` and `scripts/` for the reproducible pipeline

## What the project demonstrates

BRAVO Lab demonstrates a complete research workflow:

- public market data ingestion
- Brazilian equity risk measurement
- realized volatility and drawdown diagnostics
- regime classification
- synthetic option-overlay logic
- covered-call and collar comparison
- active-risk diagnostics
- multi-asset stress signals
- Brazil Stress Transmission Index construction
- threshold validation
- calibration logic
- policy-selection logic
- report automation
- reproducible research packaging

## How to test the project

A reviewer can inspect the repository, rerun the pipeline, regenerate processed evidence, recreate figures, and rebuild the executive report.

The project is intentionally transparent: the report is not only a PDF. It is backed by code, processed outputs, figures, and a reproducible workflow.

## Current methodological status

The current version does not yet implement GARCH, MTV-GARCH, CCA, wavelets, or machine learning. Those are future extensions. The current version is a transparent v0.1 baseline using realized volatility, drawdown regimes, synthetic option overlays, active-risk diagnostics, and the BSTI stress-transmission framework.

## Production limitations

The derivative layer is synthetic. Real listed-option data, bid-ask spreads, liquidity filters, tax treatment, roll rules, and execution constraints must be integrated before any live trading or production claim.


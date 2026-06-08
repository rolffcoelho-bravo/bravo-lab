# BRAVO Lab v0.1.0 Release Notes

## Release identity

BRAVO Lab v0.1.0 is the first stable public milestone of the Brazilian Risk, Allocation, Volatility & Options Lab.

This release turns the project from a repository scaffold into a working quant/risk evidence package with reproducible outputs, premium visual diagnostics, a front-office memo layer, processed CSV evidence, offline tests, GitHub Actions CI, and a Windows-friendly report runner.

## What is included

| Layer | Status |
| --- | --- |
| Data and processed evidence outputs | Included |
| Baseline market-risk report | Included |
| Brazil Stress Transmission Index | Included |
| BSTI threshold validation | Included |
| BSTI calibration layer | Included |
| BSTI overlay policy selection | Included |
| BSTI persistence and transition diagnostics | Included |
| Synthetic covered call and collar overlay logic | Included |
| Active-risk and drawdown diagnostics | Included |
| Premium visual evidence layer | Included |
| Front-office executive memo | Included |
| Standalone report index | Included |
| Offline smoke tests | Included |
| GitHub Actions CI | Included |
| Windows-friendly report runner | Included |

## Main entry points

| File | Purpose |
| --- | --- |
| README.md | Main project landing page |
| reports/front_office_memo.md | Fast portfolio-governance memo |
| reports/baseline_report.md | Full decision-grade report |
| reports/README.md | Report navigation guide |
| reports/figures/00_executive_risk_dashboard.png | Executive visual dashboard |
| scripts/generate_report.py | Windows-friendly report generator |

## How to reproduce

Windows PowerShell:

python -m pip install -r requirements.txt
$env:PYTHONPATH="src"
python -m pytest -q
python scripts/generate_report.py

macOS / Linux:

python -m pip install -r requirements.txt
PYTHONPATH=src pytest -q
PYTHONPATH=src python scripts/generate_report.py

## Current limitations

This is not investment advice, not a production trading system, and not a live portfolio engine.

The current release still uses synthetic option-premium logic. Real B3 option-chain data, liquidity filters, transaction-cost calibration, tax effects, slippage, and portfolio mandate constraints must be added before production use.

## Strategic value

BRAVO Lab v0.1.0 demonstrates that Brazilian market data, stress transmission logic, derivative overlay thinking, reproducible Python code, and front-office reporting can be combined into a coherent portfolio-research system.

The release is designed to be readable by recruiters, portfolio managers, risk committees, research reviewers, and technical evaluators.

"""
Configuration layer for BRAVO Lab.

This file centralizes baseline tickers, date ranges, and reporting paths.
The objective is to keep research assumptions visible and easy to modify.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

START_DATE = "2014-01-01"
END_DATE = None

TICKERS = {
    "brazil_equity": "BOVA11.SA",
    "brazil_external": "EWZ",
    "global_equity": "SPY",
    "fx_usdbrl": "BRL=X",
    "vix": "^VIX",
}

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE_ANNUAL = 0.0
BASELINE_REPORT_PATH = REPORTS_DIR / "baseline_report.md"
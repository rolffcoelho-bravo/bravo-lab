"""
Data utilities for BRAVO Lab.

This module handles basic market-data download, price cleaning, and return
construction for the first baseline version of the project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd
import yfinance as yf

from bravo.config import END_DATE, START_DATE, TICKERS


@dataclass
class MarketDataBundle:
    """Container for cleaned prices and calculated returns."""

    prices: pd.DataFrame
    returns: pd.DataFrame


def download_adjusted_prices(
    tickers: Optional[Dict[str, str]] = None,
    start: str = START_DATE,
    end: Optional[str] = END_DATE,
) -> pd.DataFrame:
    """
    Download adjusted close prices from Yahoo Finance.

    Parameters
    ----------
    tickers:
        Dictionary mapping internal asset labels to Yahoo Finance tickers.
    start:
        Start date in YYYY-MM-DD format.
    end:
        Optional end date in YYYY-MM-DD format.

    Returns
    -------
    pandas.DataFrame
        Adjusted close prices with internal labels as columns.
    """
    tickers = tickers or TICKERS
    symbols = list(tickers.values())
    label_by_symbol = {symbol: label for label, symbol in tickers.items()}

    raw = yf.download(
        tickers=symbols,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="column",
    )

    if raw.empty:
        raise ValueError("No data returned from Yahoo Finance.")

    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"].copy()
    else:
        prices = raw[["Close"]].copy()
        prices.columns = symbols

    prices = prices.rename(columns=label_by_symbol)
    prices = prices.sort_index()
    prices = prices.dropna(how="all")

    return prices


def clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Clean price data using conservative rules.

    Fully empty rows are removed, short gaps are forward-filled, and remaining
    rows with missing values are dropped to keep the baseline calculation clean.
    """
    cleaned = prices.copy()
    cleaned = cleaned.dropna(how="all")
    cleaned = cleaned.ffill(limit=5)
    cleaned = cleaned.dropna(how="any")
    return cleaned


def calculate_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate daily percentage returns from adjusted prices.
    """
    return prices.pct_change().dropna(how="any")


def load_market_data(
    tickers: Optional[Dict[str, str]] = None,
    start: str = START_DATE,
    end: Optional[str] = END_DATE,
) -> MarketDataBundle:
    """
    Download, clean, and transform market data into returns.
    """
    prices = download_adjusted_prices(tickers=tickers, start=start, end=end)
    prices = clean_prices(prices)
    returns = calculate_returns(prices)
    return MarketDataBundle(prices=prices, returns=returns)
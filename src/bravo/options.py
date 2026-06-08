"""
Option-pricing utilities for BRAVO Lab.

This module provides a transparent Black-Scholes baseline used to create
synthetic option premiums for covered call and collar strategy prototypes.

Important limitation:
This is not real B3 option-chain data. It is a research approximation used
until real listed-option data is integrated.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import norm

from bravo.config import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR


def estimate_annualized_volatility(
    returns: pd.Series,
    window: int = 63,
) -> pd.Series:
    """
    Estimate rolling annualized volatility from daily returns.
    """
    return returns.rolling(window=window).std() * np.sqrt(TRADING_DAYS_PER_YEAR)


def black_scholes_call_price(
    spot: float,
    strike: float,
    time_to_maturity_years: float,
    volatility: float,
    risk_free_rate: float = RISK_FREE_RATE_ANNUAL,
) -> float:
    """
    Price a European call option using the Black-Scholes formula.
    """
    if spot <= 0 or strike <= 0 or time_to_maturity_years <= 0:
        return np.nan

    if volatility <= 0 or np.isnan(volatility):
        return np.nan

    d1 = (
        math.log(spot / strike)
        + (risk_free_rate + 0.5 * volatility**2) * time_to_maturity_years
    ) / (volatility * math.sqrt(time_to_maturity_years))

    d2 = d1 - volatility * math.sqrt(time_to_maturity_years)

    call_price = spot * norm.cdf(d1) - strike * math.exp(
        -risk_free_rate * time_to_maturity_years
    ) * norm.cdf(d2)

    return float(call_price)


def black_scholes_put_price(
    spot: float,
    strike: float,
    time_to_maturity_years: float,
    volatility: float,
    risk_free_rate: float = RISK_FREE_RATE_ANNUAL,
) -> float:
    """
    Price a European put option using the Black-Scholes formula.
    """
    if spot <= 0 or strike <= 0 or time_to_maturity_years <= 0:
        return np.nan

    if volatility <= 0 or np.isnan(volatility):
        return np.nan

    d1 = (
        math.log(spot / strike)
        + (risk_free_rate + 0.5 * volatility**2) * time_to_maturity_years
    ) / (volatility * math.sqrt(time_to_maturity_years))

    d2 = d1 - volatility * math.sqrt(time_to_maturity_years)

    put_price = strike * math.exp(-risk_free_rate * time_to_maturity_years) * norm.cdf(
        -d2
    ) - spot * norm.cdf(-d1)

    return float(put_price)


def option_premium_fraction(
    option_price: float,
    spot: float,
) -> float:
    """
    Convert option price into a fraction of the underlying spot price.
    """
    if spot <= 0 or np.isnan(option_price):
        return np.nan

    return option_price / spot
"""
Performance and risk metrics for BRAVO Lab.

This module contains baseline portfolio metrics used in the first decision-grade
report layer. The functions are intentionally transparent and easy to audit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bravo.config import RISK_FREE_RATE_ANNUAL, TRADING_DAYS_PER_YEAR


def annualized_return(returns: pd.Series) -> float:
    """
    Calculate annualized return from daily returns.
    """
    returns = returns.dropna()
    if returns.empty:
        return np.nan

    cumulative_return = (1 + returns).prod()
    years = len(returns) / TRADING_DAYS_PER_YEAR

    if years <= 0:
        return np.nan

    return cumulative_return ** (1 / years) - 1


def annualized_volatility(returns: pd.Series) -> float:
    """
    Calculate annualized volatility from daily returns.
    """
    returns = returns.dropna()
    if returns.empty:
        return np.nan

    return returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate_annual: float = RISK_FREE_RATE_ANNUAL,
) -> float:
    """
    Calculate annualized Sharpe ratio.
    """
    returns = returns.dropna()
    if returns.empty:
        return np.nan

    daily_rf = risk_free_rate_annual / TRADING_DAYS_PER_YEAR
    excess_returns = returns - daily_rf
    volatility = excess_returns.std()

    if volatility == 0 or np.isnan(volatility):
        return np.nan

    return (excess_returns.mean() / volatility) * np.sqrt(TRADING_DAYS_PER_YEAR)


def sortino_ratio(
    returns: pd.Series,
    risk_free_rate_annual: float = RISK_FREE_RATE_ANNUAL,
) -> float:
    """
    Calculate annualized Sortino ratio using downside deviation.
    """
    returns = returns.dropna()
    if returns.empty:
        return np.nan

    daily_rf = risk_free_rate_annual / TRADING_DAYS_PER_YEAR
    excess_returns = returns - daily_rf
    downside_returns = excess_returns[excess_returns < 0]
    downside_deviation = downside_returns.std()

    if downside_deviation == 0 or np.isnan(downside_deviation):
        return np.nan

    return (excess_returns.mean() / downside_deviation) * np.sqrt(TRADING_DAYS_PER_YEAR)


def cumulative_returns(returns: pd.Series) -> pd.Series:
    """
    Calculate cumulative return series from daily returns.
    """
    return (1 + returns.dropna()).cumprod()


def drawdown_series(returns: pd.Series) -> pd.Series:
    """
    Calculate drawdown series from daily returns.
    """
    cumulative = cumulative_returns(returns)
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1
    return drawdown


def max_drawdown(returns: pd.Series) -> float:
    """
    Calculate maximum drawdown.
    """
    drawdowns = drawdown_series(returns)
    if drawdowns.empty:
        return np.nan
    return drawdowns.min()


def var_historical(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Calculate historical Value at Risk.
    """
    returns = returns.dropna()
    if returns.empty:
        return np.nan

    return returns.quantile(1 - confidence)


def cvar_historical(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Calculate historical Conditional Value at Risk.
    """
    returns = returns.dropna()
    if returns.empty:
        return np.nan

    var_level = var_historical(returns, confidence)
    tail_returns = returns[returns <= var_level]

    if tail_returns.empty:
        return np.nan

    return tail_returns.mean()


def summarize_performance(returns: pd.DataFrame) -> pd.DataFrame:
    """
    Generate a baseline performance summary for each return series.
    """
    rows = []

    for column in returns.columns:
        series = returns[column].dropna()

        rows.append(
            {
                "asset": column,
                "annualized_return": annualized_return(series),
                "annualized_volatility": annualized_volatility(series),
                "sharpe_ratio": sharpe_ratio(series),
                "sortino_ratio": sortino_ratio(series),
                "max_drawdown": max_drawdown(series),
                "historical_var_95": var_historical(series, confidence=0.95),
                "historical_cvar_95": cvar_historical(series, confidence=0.95),
                "observations": len(series),
            }
        )

    return pd.DataFrame(rows).set_index("asset")
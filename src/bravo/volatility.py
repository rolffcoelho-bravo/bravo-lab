"""
Volatility and regime utilities for BRAVO Lab.

This module starts with transparent realized-volatility and drawdown-based
regime logic. More advanced GARCH and MTV-GARCH layers will be added after the
baseline pipeline is working and testable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bravo.config import TRADING_DAYS_PER_YEAR


def realized_volatility(
    returns: pd.Series,
    window: int = 21,
    annualize: bool = True,
) -> pd.Series:
    """
    Calculate rolling realized volatility.
    """
    volatility = returns.rolling(window=window).std()

    if annualize:
        volatility = volatility * np.sqrt(TRADING_DAYS_PER_YEAR)

    return volatility


def rolling_drawdown(returns: pd.Series) -> pd.Series:
    """
    Calculate rolling drawdown from daily returns.
    """
    cumulative = (1 + returns.dropna()).cumprod()
    running_max = cumulative.cummax()
    return cumulative / running_max - 1


def volatility_percentile(
    volatility: pd.Series,
    window: int = 252,
) -> pd.Series:
    """
    Calculate rolling percentile rank of volatility.

    The output is between 0 and 1. Higher values indicate higher volatility
    relative to the recent historical window.
    """

    def percentile_rank(values: np.ndarray) -> float:
        current_value = values[-1]
        return np.sum(values <= current_value) / len(values)

    return volatility.rolling(window=window).apply(percentile_rank, raw=True)


def classify_regime(
    volatility_pct: pd.Series,
    drawdown: pd.Series,
) -> pd.Series:
    """
    Classify market regime using volatility percentile and drawdown.

    This is a transparent baseline classifier. It is not intended to be final.
    Later versions should compare this against GARCH, MTV-GARCH, and contagion
    indicators.
    """
    aligned = pd.concat(
        {
            "volatility_pct": volatility_pct,
            "drawdown": drawdown,
        },
        axis=1,
    ).dropna()

    regime = pd.Series(index=aligned.index, dtype="object")

    calm_mask = (aligned["volatility_pct"] < 0.40) & (aligned["drawdown"] > -0.05)
    fragile_mask = (
        (aligned["volatility_pct"] >= 0.40)
        & (aligned["volatility_pct"] < 0.65)
        & (aligned["drawdown"] > -0.10)
    )
    stress_mask = (
        (aligned["volatility_pct"] >= 0.65)
        | ((aligned["drawdown"] <= -0.10) & (aligned["drawdown"] > -0.20))
    )
    extreme_mask = (aligned["volatility_pct"] >= 0.85) | (aligned["drawdown"] <= -0.20)

    regime.loc[calm_mask] = "calm"
    regime.loc[fragile_mask] = "fragile"
    regime.loc[stress_mask] = "stress"
    regime.loc[extreme_mask] = "extreme_stress"

    regime = regime.fillna("neutral")

    return regime


def build_baseline_regime_table(
    returns: pd.Series,
    volatility_window: int = 21,
    percentile_window: int = 252,
) -> pd.DataFrame:
    """
    Build a baseline regime table for one return series.
    """
    vol = realized_volatility(returns, window=volatility_window)
    vol_pct = volatility_percentile(vol, window=percentile_window)
    dd = rolling_drawdown(returns)
    regime = classify_regime(vol_pct, dd)

    table = pd.concat(
        {
            "returns": returns,
            "realized_volatility": vol,
            "volatility_percentile": vol_pct,
            "drawdown": dd,
            "regime": regime,
        },
        axis=1,
    ).dropna()

    return table
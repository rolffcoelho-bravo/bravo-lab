"""
Multi-asset stress-signal layer for BRAVO Lab.

This module builds stress inputs beyond the local Brazilian equity price series.
It uses the public market-data universe already downloaded by the project:

- BOVA11.SA as local Brazilian equity exposure
- EWZ as external Brazil equity pressure
- SPY as global equity pressure
- BRL=X as USD/BRL FX pressure
- ^VIX as global volatility pressure

The purpose is not to forecast markets. The purpose is to create an interpretable
stress dashboard that can support portfolio discussion, overlay governance, and
future Brazil Stress Transmission Index development.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_zscore(
    series: pd.Series,
    window: int = 63,
    min_periods: int = 21,
    clip_value: float = 3.0,
) -> pd.Series:
    """
    Calculate a rolling z-score with clipping for stability.
    """
    clean = series.astype(float)

    rolling_mean = clean.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = clean.rolling(window=window, min_periods=min_periods).std(ddof=1)

    zscore = (clean - rolling_mean) / rolling_std.replace(0.0, np.nan)

    return zscore.clip(lower=-clip_value, upper=clip_value)


def positive_pressure_score(zscore: pd.Series) -> pd.Series:
    """
    Keep only positive pressure from a z-score.

    Negative values are set to zero because this layer is designed as a stress
    dashboard, not a two-sided return signal.
    """
    return zscore.clip(lower=0.0)


def rolling_drawdown(prices: pd.Series) -> pd.Series:
    """
    Calculate drawdown from running peak.
    """
    clean = prices.dropna().astype(float)

    cumulative = clean / clean.iloc[0]
    running_peak = cumulative.cummax()

    return cumulative / running_peak - 1.0


def build_stress_signal_table(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    window: int = 63,
    min_periods: int = 21,
) -> pd.DataFrame:
    """
    Build a multi-asset stress-signal table.

    Required return columns:
    - brazil_equity
    - brazil_external
    - global_equity
    - fx_usdbrl
    - vix

    Required price columns:
    - brazil_equity
    - vix

    The output includes individual pressure scores and a composite stress score.
    """
    required_return_columns = [
        "brazil_equity",
        "brazil_external",
        "global_equity",
        "fx_usdbrl",
        "vix",
    ]

    required_price_columns = [
        "brazil_equity",
        "vix",
    ]

    missing_returns = [col for col in required_return_columns if col not in returns.columns]
    missing_prices = [col for col in required_price_columns if col not in prices.columns]

    if missing_returns:
        raise KeyError(f"Missing return columns: {missing_returns}")

    if missing_prices:
        raise KeyError(f"Missing price columns: {missing_prices}")

    aligned_returns = returns[required_return_columns].dropna(how="all").copy()
    aligned_prices = prices[required_price_columns].dropna(how="all").copy()

    common_index = aligned_returns.index.intersection(aligned_prices.index)

    aligned_returns = aligned_returns.loc[common_index]
    aligned_prices = aligned_prices.loc[common_index]

    table = pd.DataFrame(index=common_index)

    brazil_drawdown = rolling_drawdown(aligned_prices["brazil_equity"]).reindex(common_index)
    brazil_realized_vol = (
        aligned_returns["brazil_equity"]
        .rolling(window=21, min_periods=10)
        .std(ddof=1)
        * np.sqrt(252)
    )

    ewz_vs_spy = aligned_returns["brazil_external"] - aligned_returns["global_equity"]

    table["brazil_equity_return"] = aligned_returns["brazil_equity"]
    table["brazil_drawdown"] = brazil_drawdown
    table["brazil_realized_vol_21d"] = brazil_realized_vol
    table["ewz_vs_spy_return"] = ewz_vs_spy
    table["global_equity_return"] = aligned_returns["global_equity"]
    table["fx_usdbrl_return"] = aligned_returns["fx_usdbrl"]
    table["vix_return"] = aligned_returns["vix"]
    table["vix_level"] = aligned_prices["vix"]

    table["brazil_drawdown_pressure"] = positive_pressure_score(
        rolling_zscore(-table["brazil_drawdown"], window=window, min_periods=min_periods)
    )

    table["brazil_vol_pressure"] = positive_pressure_score(
        rolling_zscore(table["brazil_realized_vol_21d"], window=window, min_periods=min_periods)
    )

    table["external_brazil_pressure"] = positive_pressure_score(
        rolling_zscore(-table["ewz_vs_spy_return"], window=window, min_periods=min_periods)
    )

    table["global_equity_pressure"] = positive_pressure_score(
        rolling_zscore(-table["global_equity_return"], window=window, min_periods=min_periods)
    )

    table["fx_pressure"] = positive_pressure_score(
        rolling_zscore(table["fx_usdbrl_return"], window=window, min_periods=min_periods)
    )

    table["vix_pressure"] = positive_pressure_score(
        rolling_zscore(table["vix_return"], window=window, min_periods=min_periods)
    )

    pressure_columns = [
        "brazil_drawdown_pressure",
        "brazil_vol_pressure",
        "external_brazil_pressure",
        "global_equity_pressure",
        "fx_pressure",
        "vix_pressure",
    ]

    table["multi_asset_stress_score"] = table[pressure_columns].mean(axis=1)

    table["multi_asset_stress_regime"] = classify_multi_asset_stress(
        table["multi_asset_stress_score"]
    )

    return table


def classify_multi_asset_stress(
    stress_score: pd.Series,
) -> pd.Series:
    """
    Classify the composite stress score into interpretable regimes.

    Thresholds are intentionally simple and stable:
    - calm: below 0.50
    - fragile: 0.50 to 1.00
    - stress: 1.00 to 1.50
    - extreme_stress: above 1.50

    Because each component is a clipped positive z-score, values above 1.00
    indicate broad stress pressure rather than one isolated noisy move.
    """
    def classify(value: float) -> str:
        if pd.isna(value):
            return "neutral"
        if value >= 1.50:
            return "extreme_stress"
        if value >= 1.00:
            return "stress"
        if value >= 0.50:
            return "fragile"
        return "calm"

    return stress_score.apply(classify)


def stress_signal_summary(
    stress_table: pd.DataFrame,
) -> pd.DataFrame:
    """
    Summarize the current multi-asset stress dashboard.
    """
    if stress_table.empty:
        return pd.DataFrame()

    latest = stress_table.dropna(subset=["multi_asset_stress_score"]).tail(1)

    if latest.empty:
        return pd.DataFrame()

    row = latest.iloc[0]

    pressure_columns = [
        "brazil_drawdown_pressure",
        "brazil_vol_pressure",
        "external_brazil_pressure",
        "global_equity_pressure",
        "fx_pressure",
        "vix_pressure",
    ]

    ranked = row[pressure_columns].sort_values(ascending=False)

    return pd.DataFrame(
        [
            {
                "date": latest.index[0],
                "multi_asset_stress_score": row["multi_asset_stress_score"],
                "multi_asset_stress_regime": row["multi_asset_stress_regime"],
                "top_pressure_1": ranked.index[0],
                "top_pressure_1_value": ranked.iloc[0],
                "top_pressure_2": ranked.index[1],
                "top_pressure_2_value": ranked.iloc[1],
                "top_pressure_3": ranked.index[2],
                "top_pressure_3_value": ranked.iloc[2],
                "brazil_drawdown": row["brazil_drawdown"],
                "brazil_realized_vol_21d": row["brazil_realized_vol_21d"],
                "vix_level": row["vix_level"],
            }
        ]
    )


def stress_signal_interpretation(summary: pd.DataFrame) -> str:
    """
    Produce a compact interpretation of the latest stress-signal dashboard.
    """
    if summary.empty:
        return (
            "No multi-asset stress summary was available. The stress dashboard "
            "requires valid BOVA11, EWZ, SPY, USD/BRL, and VIX data."
        )

    row = summary.iloc[0]

    return (
        f"Multi-asset stress read: the latest composite stress score is "
        f"`{row['multi_asset_stress_score']:.2f}`, classified as "
        f"`{row['multi_asset_stress_regime']}`. The strongest current pressure "
        f"inputs are `{row['top_pressure_1']}`, `{row['top_pressure_2']}`, and "
        f"`{row['top_pressure_3']}`. This extends the framework beyond local price "
        "behavior and starts moving BRAVO Lab toward a broader Brazil stress "
        "transmission dashboard."
    )

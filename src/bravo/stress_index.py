"""
Brazil Stress Transmission Index for BRAVO Lab.

This module converts the multi-asset stress dashboard into a formal composite
index. The index is designed for portfolio-governance discussion, not market
forecasting.

Inputs come from the multi-asset stress signal table:

- local Brazilian equity drawdown pressure
- local Brazilian equity volatility pressure
- external Brazil pressure through EWZ versus SPY
- global equity pressure through SPY
- USD/BRL FX pressure
- VIX pressure

The output is a 0 to 100 Brazil Stress Transmission Index, with regime labels,
channel contributions, dominant pressure channel, and stress breadth.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_BSTI_WEIGHTS: dict[str, float] = {
    "brazil_drawdown_pressure": 0.20,
    "brazil_vol_pressure": 0.15,
    "external_brazil_pressure": 0.20,
    "global_equity_pressure": 0.15,
    "fx_pressure": 0.15,
    "vix_pressure": 0.15,
}


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """
    Normalize component weights so they sum to one.
    """
    if not weights:
        raise ValueError("Weights cannot be empty.")

    total = sum(float(value) for value in weights.values())

    if np.isclose(total, 0.0):
        raise ValueError("Weights must not sum to zero.")

    return {key: float(value) / total for key, value in weights.items()}


def classify_bsti_regime(index_value: float) -> str:
    """
    Classify the 0 to 100 Brazil Stress Transmission Index.

    Thresholds:
    - calm: below 15
    - fragile: 15 to 33
    - stress: 33 to 50
    - extreme_stress: above 50

    These thresholds map to the underlying positive z-score logic where
    0.50, 1.00, and 1.50 define increasingly broad stress pressure.
    """
    if pd.isna(index_value):
        return "neutral"

    if index_value >= 50.0:
        return "extreme_stress"

    if index_value >= 33.0:
        return "stress"

    if index_value >= 15.0:
        return "fragile"

    return "calm"


def build_brazil_stress_transmission_index(
    stress_signal_table: pd.DataFrame,
    weights: dict[str, float] | None = None,
    max_component_score: float = 3.0,
    breadth_threshold: float = 0.75,
) -> pd.DataFrame:
    """
    Build the Brazil Stress Transmission Index.

    The raw index is a weighted average of positive pressure z-scores.
    The 0 to 100 index rescales the raw score by the maximum clipped component
    score used in the stress-signal layer.
    """
    if stress_signal_table.empty:
        return pd.DataFrame()

    weights = normalize_weights(weights or DEFAULT_BSTI_WEIGHTS)

    missing_columns = [
        column for column in weights.keys() if column not in stress_signal_table.columns
    ]

    if missing_columns:
        raise KeyError(f"Missing stress-signal columns: {missing_columns}")

    table = stress_signal_table.copy()

    index = pd.DataFrame(index=table.index)

    weighted_columns = []

    for column, weight in weights.items():
        contribution_column = f"{column}_weighted"
        index[contribution_column] = table[column].fillna(0.0) * weight
        weighted_columns.append(contribution_column)

    index["bsti_raw_score"] = index[weighted_columns].sum(axis=1)

    index["bsti_0_100"] = (
        index["bsti_raw_score"] / max_component_score * 100.0
    ).clip(lower=0.0, upper=100.0)

    index["bsti_regime"] = index["bsti_0_100"].apply(classify_bsti_regime)

    component_frame = table[list(weights.keys())].fillna(0.0)

    index["stress_breadth"] = (
        component_frame.gt(breadth_threshold).sum(axis=1) / len(weights)
    )

    index["active_pressure_channels"] = component_frame.gt(breadth_threshold).sum(axis=1)

    index["dominant_pressure_channel"] = component_frame.idxmax(axis=1)

    index["dominant_pressure_value"] = component_frame.max(axis=1)

    for column in weights.keys():
        index[column] = table[column]

    return index


def bsti_component_summary(
    bsti_table: pd.DataFrame,
) -> pd.DataFrame:
    """
    Summarize latest Brazil Stress Transmission Index state.
    """
    if bsti_table.empty:
        return pd.DataFrame()

    latest = bsti_table.dropna(subset=["bsti_0_100"]).tail(1)

    if latest.empty:
        return pd.DataFrame()

    row = latest.iloc[0]

    component_columns = list(DEFAULT_BSTI_WEIGHTS.keys())
    ranked = row[component_columns].sort_values(ascending=False)

    return pd.DataFrame(
        [
            {
                "date": latest.index[0],
                "bsti_0_100": row["bsti_0_100"],
                "bsti_raw_score": row["bsti_raw_score"],
                "bsti_regime": row["bsti_regime"],
                "stress_breadth": row["stress_breadth"],
                "active_pressure_channels": row["active_pressure_channels"],
                "dominant_pressure_channel": row["dominant_pressure_channel"],
                "dominant_pressure_value": row["dominant_pressure_value"],
                "top_channel_1": ranked.index[0],
                "top_channel_1_value": ranked.iloc[0],
                "top_channel_2": ranked.index[1],
                "top_channel_2_value": ranked.iloc[1],
                "top_channel_3": ranked.index[2],
                "top_channel_3_value": ranked.iloc[2],
            }
        ]
    )


def bsti_regime_distribution(
    bsti_table: pd.DataFrame,
) -> pd.DataFrame:
    """
    Count the historical distribution of BSTI regimes.
    """
    if bsti_table.empty or "bsti_regime" not in bsti_table.columns:
        return pd.DataFrame()

    counts = bsti_table["bsti_regime"].value_counts(dropna=False)
    shares = bsti_table["bsti_regime"].value_counts(normalize=True, dropna=False)

    summary = pd.DataFrame(
        {
            "observations": counts,
            "share": shares,
        }
    )

    summary.index.name = "bsti_regime"

    return summary.reset_index()


def bsti_interpretation(
    summary: pd.DataFrame,
) -> str:
    """
    Produce a compact interpretation of the latest BSTI state.
    """
    if summary.empty:
        return (
            "No Brazil Stress Transmission Index summary was available. The index "
            "requires a valid multi-asset stress-signal table."
        )

    row = summary.iloc[0]

    return (
        f"BSTI read: the latest Brazil Stress Transmission Index is "
        f"`{row['bsti_0_100']:.1f}` out of 100, classified as "
        f"`{row['bsti_regime']}`. Stress breadth is "
        f"`{row['stress_breadth']:.2f}`, with "
        f"`{int(row['active_pressure_channels'])}` active pressure channels. "
        f"The dominant pressure channel is `{row['dominant_pressure_channel']}`. "
        f"The top three channels are `{row['top_channel_1']}`, "
        f"`{row['top_channel_2']}`, and `{row['top_channel_3']}`. This turns the "
        "multi-asset stress dashboard into a formal Brazil stress-transmission "
        "index that can be monitored, reported, and later tested against overlay "
        "decisions."
    )

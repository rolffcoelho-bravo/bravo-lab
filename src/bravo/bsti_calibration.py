"""
BSTI calibration layer for BRAVO Lab.

This module tests alternative Brazil Stress Transmission Index thresholds and
component-weighting schemes.

The purpose is not to overfit the index. The purpose is to show whether the
chosen BSTI structure is robust enough for portfolio-governance discussion.

It compares alternative weighting schemes against forward benchmark outcomes,
future drawdown events, and signal frequency.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bravo.bsti_validation import (
    build_bsti_forward_outcomes,
    bsti_threshold_validation,
)
from bravo.stress_index import build_brazil_stress_transmission_index


DEFAULT_CALIBRATION_THRESHOLDS: tuple[float, ...] = (
    10.0,
    15.0,
    20.0,
    25.0,
    33.0,
    40.0,
    50.0,
)


def default_bsti_weight_schemes() -> dict[str, dict[str, float]]:
    """
    Return alternative BSTI weighting schemes.

    Each scheme keeps the same pressure channels but changes emphasis.
    """
    return {
        "balanced": {
            "brazil_drawdown_pressure": 0.20,
            "brazil_vol_pressure": 0.15,
            "external_brazil_pressure": 0.20,
            "global_equity_pressure": 0.15,
            "fx_pressure": 0.15,
            "vix_pressure": 0.15,
        },
        "local_risk_heavy": {
            "brazil_drawdown_pressure": 0.30,
            "brazil_vol_pressure": 0.25,
            "external_brazil_pressure": 0.15,
            "global_equity_pressure": 0.10,
            "fx_pressure": 0.10,
            "vix_pressure": 0.10,
        },
        "external_brazil_heavy": {
            "brazil_drawdown_pressure": 0.15,
            "brazil_vol_pressure": 0.10,
            "external_brazil_pressure": 0.35,
            "global_equity_pressure": 0.15,
            "fx_pressure": 0.15,
            "vix_pressure": 0.10,
        },
        "fx_vix_heavy": {
            "brazil_drawdown_pressure": 0.15,
            "brazil_vol_pressure": 0.10,
            "external_brazil_pressure": 0.15,
            "global_equity_pressure": 0.10,
            "fx_pressure": 0.25,
            "vix_pressure": 0.25,
        },
        "global_risk_heavy": {
            "brazil_drawdown_pressure": 0.15,
            "brazil_vol_pressure": 0.10,
            "external_brazil_pressure": 0.15,
            "global_equity_pressure": 0.30,
            "fx_pressure": 0.10,
            "vix_pressure": 0.20,
        },
    }


def _calibration_governance_score(row: pd.Series) -> float:
    """
    Build a simple governance score for threshold comparison.

    Higher is better.

    The score rewards:
    - high 5 percent drawdown precision
    - high 5 percent drawdown recall
    - worse forward drawdowns when signal is on versus off

    It penalizes:
    - signals that are too frequent and therefore less selective
    """
    precision = row.get("future_drawdown_5pct_precision", np.nan)
    recall = row.get("future_drawdown_5pct_recall", np.nan)
    signal_frequency = row.get("signal_frequency", np.nan)

    drawdown_on = row.get("avg_forward_max_drawdown_signal_on", np.nan)
    drawdown_off = row.get("avg_forward_max_drawdown_signal_off", np.nan)

    precision = 0.0 if pd.isna(precision) else float(precision)
    recall = 0.0 if pd.isna(recall) else float(recall)
    signal_frequency = 0.0 if pd.isna(signal_frequency) else float(signal_frequency)

    if pd.isna(drawdown_on) or pd.isna(drawdown_off):
        drawdown_separation = 0.0
    else:
        drawdown_separation = float(drawdown_off - drawdown_on)

    return (
        0.45 * precision
        + 0.30 * recall
        + 0.20 * drawdown_separation
        - 0.10 * signal_frequency
    )


def build_bsti_calibration_grid(
    stress_signal_table: pd.DataFrame,
    benchmark_returns: pd.Series,
    weight_schemes: dict[str, dict[str, float]] | None = None,
    thresholds: tuple[float, ...] = DEFAULT_CALIBRATION_THRESHOLDS,
    horizons: tuple[int, ...] = (21, 63),
) -> pd.DataFrame:
    """
    Test alternative BSTI weights and thresholds against forward outcomes.
    """
    if stress_signal_table.empty:
        return pd.DataFrame()

    schemes = weight_schemes or default_bsti_weight_schemes()

    rows = []

    for scheme_name, weights in schemes.items():
        bsti_table = build_brazil_stress_transmission_index(
            stress_signal_table=stress_signal_table,
            weights=weights,
        )

        forward_outcomes = build_bsti_forward_outcomes(
            bsti_table=bsti_table,
            benchmark_returns=benchmark_returns,
            horizons=horizons,
        )

        validation = bsti_threshold_validation(
            forward_outcomes=forward_outcomes,
            thresholds=thresholds,
        )

        if validation.empty:
            continue

        validation = validation.copy()
        validation["weight_scheme"] = scheme_name

        for _, row in validation.iterrows():
            row_dict = row.to_dict()
            row_dict["governance_score"] = _calibration_governance_score(row)
            rows.append(row_dict)

    if not rows:
        return pd.DataFrame()

    columns_order = [
        "weight_scheme",
        "horizon_days",
        "bsti_threshold",
        "governance_score",
        "observations",
        "signal_observations",
        "signal_frequency",
        "avg_forward_return_signal_on",
        "avg_forward_return_signal_off",
        "avg_forward_max_drawdown_signal_on",
        "avg_forward_max_drawdown_signal_off",
        "future_negative_return_precision",
        "future_drawdown_5pct_precision",
        "future_drawdown_10pct_precision",
        "future_negative_return_recall",
        "future_drawdown_5pct_recall",
        "future_drawdown_10pct_recall",
    ]

    result = pd.DataFrame(rows)

    existing_columns = [col for col in columns_order if col in result.columns]
    remaining_columns = [col for col in result.columns if col not in existing_columns]

    return result[existing_columns + remaining_columns]


def best_bsti_calibration_by_horizon(
    calibration_grid: pd.DataFrame,
) -> pd.DataFrame:
    """
    Select the best calibration candidate for each forward horizon.
    """
    if calibration_grid.empty:
        return pd.DataFrame()

    rows = []

    for horizon, data in calibration_grid.groupby("horizon_days"):
        valid = data.dropna(subset=["governance_score"])

        if valid.empty:
            continue

        best = valid.loc[valid["governance_score"].idxmax()].copy()
        best["selection_rule"] = "max_governance_score"
        rows.append(best)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).reset_index(drop=True)


def bsti_calibration_interpretation(
    best_calibration: pd.DataFrame,
) -> str:
    """
    Produce a compact interpretation of the calibration results.
    """
    if best_calibration.empty:
        return (
            "No BSTI calibration result was available. The calibration layer needs "
            "valid multi-asset stress signals and forward benchmark outcomes."
        )

    best_row = best_calibration.sort_values(
        "governance_score",
        ascending=False,
    ).iloc[0]

    return (
        f"BSTI calibration read: the strongest candidate is the "
        f"`{best_row['weight_scheme']}` weighting scheme with threshold "
        f"`{best_row['bsti_threshold']}` over the "
        f"`{int(best_row['horizon_days'])}` trading-day horizon. Its governance "
        f"score is `{best_row['governance_score']:.3f}`. This does not mean the "
        "index is optimized for prediction. It means the project now tests whether "
        "different stress-channel weights and alert thresholds produce more useful "
        "portfolio-governance signals."
    )

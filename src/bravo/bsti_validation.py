"""
BSTI threshold validation for BRAVO Lab.

This module tests whether the Brazil Stress Transmission Index is useful as a
decision-grade stress signal.

It validates BSTI thresholds against:

- future benchmark returns
- future benchmark drawdowns
- future drawdown events
- overlay active returns
- stress-aware strategy behavior

The purpose is not to claim forecast power. The purpose is to test whether the
index is informative enough for portfolio-governance discussion.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_BSTI_THRESHOLDS: tuple[float, ...] = (15.0, 33.0, 50.0)


def _safe_ratio(
    numerator: float,
    denominator: float,
) -> float:
    """
    Divide safely and return NaN when the denominator is zero.
    """
    if denominator == 0 or np.isclose(denominator, 0.0):
        return np.nan

    return numerator / denominator


def _latest_value_at_or_before(
    series: pd.Series,
    date: pd.Timestamp,
) -> float | str:
    """
    Return the latest available value at or before a target date.
    """
    clean = series.dropna().sort_index()
    available = clean.loc[clean.index <= date]

    if available.empty:
        return np.nan

    return available.iloc[-1]


def build_bsti_forward_outcomes(
    bsti_table: pd.DataFrame,
    benchmark_returns: pd.Series,
    horizons: tuple[int, ...] = (21, 63),
    min_future_obs: int = 10,
) -> pd.DataFrame:
    """
    Build forward benchmark outcomes after each BSTI observation.

    For each date and each horizon, the function calculates:

    - forward benchmark return
    - forward max drawdown
    - whether a 5 percent future drawdown occurred
    - whether a 10 percent future drawdown occurred
    - whether the forward return was negative
    """
    required_columns = ["bsti_0_100", "bsti_regime"]

    missing_columns = [col for col in required_columns if col not in bsti_table.columns]

    if missing_columns:
        raise KeyError(f"Missing BSTI columns: {missing_columns}")

    bsti = bsti_table.dropna(subset=["bsti_0_100"]).sort_index()
    returns = benchmark_returns.dropna().sort_index()

    common_dates = bsti.index.intersection(returns.index)

    rows = []

    for date in common_dates:
        position = returns.index.get_loc(date)

        if isinstance(position, slice):
            position = position.start

        for horizon in horizons:
            future = returns.iloc[position + 1 : position + 1 + horizon].dropna()

            if len(future) < min_future_obs:
                continue

            future_cumulative = (1.0 + future).cumprod()

            path = pd.concat(
                [
                    pd.Series([1.0], index=[date]),
                    future_cumulative,
                ]
            )

            running_peak = path.cummax()
            forward_drawdown_path = path / running_peak - 1.0

            forward_return = future_cumulative.iloc[-1] - 1.0
            forward_max_drawdown = forward_drawdown_path.min()

            rows.append(
                {
                    "date": date,
                    "horizon_days": horizon,
                    "bsti_0_100": bsti.loc[date, "bsti_0_100"],
                    "bsti_regime": bsti.loc[date, "bsti_regime"],
                    "forward_return": forward_return,
                    "forward_max_drawdown": forward_max_drawdown,
                    "future_negative_return": forward_return < 0.0,
                    "future_drawdown_5pct": forward_max_drawdown <= -0.05,
                    "future_drawdown_10pct": forward_max_drawdown <= -0.10,
                    "future_observations": len(future),
                }
            )

    return pd.DataFrame(rows)


def bsti_threshold_validation(
    forward_outcomes: pd.DataFrame,
    thresholds: tuple[float, ...] = DEFAULT_BSTI_THRESHOLDS,
) -> pd.DataFrame:
    """
    Validate BSTI thresholds against forward return and drawdown outcomes.

    The table shows whether higher BSTI levels are associated with weaker future
    returns, deeper future drawdowns, and higher future loss-event frequency.
    """
    if forward_outcomes.empty:
        return pd.DataFrame()

    rows = []

    for horizon, horizon_data in forward_outcomes.groupby("horizon_days"):
        for threshold in thresholds:
            signal_on = horizon_data["bsti_0_100"] >= threshold
            signal_data = horizon_data[signal_on]
            no_signal_data = horizon_data[~signal_on]

            future_drawdown_5 = horizon_data["future_drawdown_5pct"]
            future_drawdown_10 = horizon_data["future_drawdown_10pct"]
            future_negative = horizon_data["future_negative_return"]

            drawdown_5_events = future_drawdown_5.sum()
            drawdown_10_events = future_drawdown_10.sum()
            negative_return_events = future_negative.sum()

            rows.append(
                {
                    "horizon_days": horizon,
                    "bsti_threshold": threshold,
                    "observations": len(horizon_data),
                    "signal_observations": len(signal_data),
                    "signal_frequency": signal_on.mean(),
                    "avg_forward_return_signal_on": signal_data[
                        "forward_return"
                    ].mean(),
                    "avg_forward_return_signal_off": no_signal_data[
                        "forward_return"
                    ].mean(),
                    "avg_forward_max_drawdown_signal_on": signal_data[
                        "forward_max_drawdown"
                    ].mean(),
                    "avg_forward_max_drawdown_signal_off": no_signal_data[
                        "forward_max_drawdown"
                    ].mean(),
                    "future_negative_return_precision": signal_data[
                        "future_negative_return"
                    ].mean(),
                    "future_drawdown_5pct_precision": signal_data[
                        "future_drawdown_5pct"
                    ].mean(),
                    "future_drawdown_10pct_precision": signal_data[
                        "future_drawdown_10pct"
                    ].mean(),
                    "future_negative_return_recall": _safe_ratio(
                        horizon_data.loc[signal_on, "future_negative_return"].sum(),
                        negative_return_events,
                    ),
                    "future_drawdown_5pct_recall": _safe_ratio(
                        horizon_data.loc[signal_on, "future_drawdown_5pct"].sum(),
                        drawdown_5_events,
                    ),
                    "future_drawdown_10pct_recall": _safe_ratio(
                        horizon_data.loc[signal_on, "future_drawdown_10pct"].sum(),
                        drawdown_10_events,
                    ),
                }
            )

    return pd.DataFrame(rows)


def bsti_overlay_threshold_validation(
    bsti_table: pd.DataFrame,
    strategy_returns: pd.DataFrame,
    benchmark_column: str = "passive_brazil_equity",
    thresholds: tuple[float, ...] = DEFAULT_BSTI_THRESHOLDS,
    periods_per_year: float = 12.0,
) -> pd.DataFrame:
    """
    Validate overlay active returns when BSTI is above selected thresholds.

    This asks whether each overlay behaves differently when the stress index is
    elevated.
    """
    if bsti_table.empty or strategy_returns.empty:
        return pd.DataFrame()

    if benchmark_column not in strategy_returns.columns:
        raise KeyError(f"Benchmark column not found: {benchmark_column}")

    if "bsti_0_100" not in bsti_table.columns:
        raise KeyError("BSTI table must contain bsti_0_100.")

    bsti_score = bsti_table["bsti_0_100"].dropna().sort_index()

    aligned_bsti = pd.Series(index=strategy_returns.index, dtype=float)

    for date in strategy_returns.index:
        aligned_bsti.loc[date] = _latest_value_at_or_before(bsti_score, date)

    combined = strategy_returns.copy()
    combined["bsti_0_100"] = aligned_bsti

    rows = []

    for threshold in thresholds:
        threshold_data = combined[combined["bsti_0_100"] >= threshold]

        if threshold_data.empty:
            continue

        benchmark = threshold_data[benchmark_column]

        for strategy in [
            col
            for col in strategy_returns.columns
            if col != benchmark_column
        ]:
            aligned = pd.concat(
                {
                    "strategy": threshold_data[strategy],
                    "benchmark": benchmark,
                },
                axis=1,
            ).dropna()

            if aligned.empty:
                continue

            active = aligned["strategy"] - aligned["benchmark"]

            tracking_error = active.std(ddof=1) * np.sqrt(periods_per_year)
            annualized_active_return = active.mean() * periods_per_year

            information_ratio = np.nan
            if not np.isclose(tracking_error, 0.0):
                information_ratio = annualized_active_return / tracking_error

            rows.append(
                {
                    "bsti_threshold": threshold,
                    "strategy": strategy,
                    "observations": len(aligned),
                    "avg_active_return": active.mean(),
                    "annualized_active_return": annualized_active_return,
                    "tracking_error": tracking_error,
                    "information_ratio": information_ratio,
                    "hit_rate_vs_passive": (
                        aligned["strategy"] > aligned["benchmark"]
                    ).mean(),
                    "best_active_period": active.max(),
                    "worst_active_period": active.min(),
                }
            )

    return pd.DataFrame(rows)


def bsti_validation_interpretation(
    threshold_validation: pd.DataFrame,
    overlay_validation: pd.DataFrame,
) -> str:
    """
    Produce a compact interpretation of BSTI validation results.
    """
    if threshold_validation.empty and overlay_validation.empty:
        return (
            "No BSTI validation results were available. The validation layer needs "
            "BSTI values, benchmark returns, and overlay return tables."
        )

    best_drawdown_threshold = "NA"
    best_drawdown_horizon = "NA"

    if not threshold_validation.empty:
        valid_drawdown = threshold_validation.dropna(
            subset=["future_drawdown_5pct_precision"]
        )

        if not valid_drawdown.empty:
            best_row = valid_drawdown.loc[
                valid_drawdown["future_drawdown_5pct_precision"].idxmax()
            ]
            best_drawdown_threshold = str(best_row["bsti_threshold"])
            best_drawdown_horizon = str(int(best_row["horizon_days"]))

    best_overlay_strategy = "NA"
    best_overlay_threshold = "NA"

    if not overlay_validation.empty:
        valid_overlay = overlay_validation.dropna(subset=["information_ratio"])

        if not valid_overlay.empty:
            best_overlay_row = valid_overlay.loc[
                valid_overlay["information_ratio"].idxmax()
            ]
            best_overlay_strategy = str(best_overlay_row["strategy"])
            best_overlay_threshold = str(best_overlay_row["bsti_threshold"])

    return (
        f"BSTI validation read: threshold `{best_drawdown_threshold}` produced the "
        f"highest 5 percent drawdown-event precision over the `{best_drawdown_horizon}` "
        "trading-day horizon. "
        f"For overlays, `{best_overlay_strategy}` showed the strongest information "
        f"ratio when BSTI was above `{best_overlay_threshold}`. This does not prove "
        "forecast power, but it starts testing whether the index is useful as a "
        "portfolio-governance warning signal rather than just a descriptive dashboard."
    )

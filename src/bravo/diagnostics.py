"""
Regime, stress-window, and strategy help-hurt diagnostics for BRAVO Lab.

This module evaluates whether overlay strategies work when they matter most:
during fragile, stress, and extreme-stress market regimes.

It also explains when each overlay helps or hurts relative to passive Brazilian
equity exposure. The purpose is to move beyond full-sample performance and test
the decision logic under market pressure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def align_regime_to_strategy_dates(
    strategy_returns: pd.DataFrame,
    regime: pd.Series,
) -> pd.Series:
    """
    Align daily regime labels to strategy return dates.

    The overlay engine produces periodic returns, usually every 21 trading days.
    The regime table is daily. This function assigns the most recent available
    regime to each strategy return date.
    """
    if strategy_returns.empty:
        return pd.Series(dtype="object")

    regime = regime.dropna().sort_index()
    aligned_regime = []

    for date in strategy_returns.index:
        available = regime.loc[regime.index <= date]

        if available.empty:
            aligned_regime.append("neutral")
        else:
            aligned_regime.append(str(available.iloc[-1]))

    return pd.Series(aligned_regime, index=strategy_returns.index, name="regime")


def regime_performance_summary(
    strategy_returns: pd.DataFrame,
    regime: pd.Series,
) -> pd.DataFrame:
    """
    Summarize strategy behavior by regime.

    This table shows whether a strategy behaves differently in calm, fragile,
    stress, and extreme-stress environments.
    """
    aligned_regime = align_regime_to_strategy_dates(strategy_returns, regime)

    combined = strategy_returns.copy()
    combined["regime"] = aligned_regime

    rows = []

    for regime_name, regime_data in combined.groupby("regime"):
        strategy_columns = [col for col in regime_data.columns if col != "regime"]

        for strategy in strategy_columns:
            series = regime_data[strategy].dropna()

            if series.empty:
                continue

            rows.append(
                {
                    "regime": regime_name,
                    "strategy": strategy,
                    "average_period_return": series.mean(),
                    "median_period_return": series.median(),
                    "best_period": series.max(),
                    "worst_period": series.min(),
                    "positive_hit_rate": (series > 0).mean(),
                    "observations": len(series),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "regime",
                "strategy",
                "average_period_return",
                "median_period_return",
                "best_period",
                "worst_period",
                "positive_hit_rate",
                "observations",
            ]
        )

    return pd.DataFrame(rows)


def stress_window_summary(
    strategy_returns: pd.DataFrame,
    regime: pd.Series,
    stress_regimes: tuple[str, ...] = ("stress", "extreme_stress"),
    benchmark_column: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Evaluate strategy behavior only during stress regimes.

    This is the key table for portfolio review because it asks whether overlays
    help when passive exposure is under pressure.
    """
    aligned_regime = align_regime_to_strategy_dates(strategy_returns, regime)

    combined = strategy_returns.copy()
    combined["regime"] = aligned_regime

    stress_data = combined[combined["regime"].isin(stress_regimes)].dropna()

    rows = []

    if stress_data.empty:
        return pd.DataFrame(
            columns=[
                "strategy",
                "average_stress_return",
                "median_stress_return",
                "worst_stress_return",
                "best_stress_return",
                "hit_rate_vs_passive_in_stress",
                "downside_protection_rate",
                "observations",
            ]
        )

    benchmark = stress_data[benchmark_column]

    for strategy in [col for col in stress_data.columns if col != "regime"]:
        series = stress_data[strategy].dropna()

        if series.empty:
            continue

        hit_rate_vs_passive = np.nan
        downside_protection_rate = np.nan

        if strategy != benchmark_column:
            aligned = pd.concat(
                {
                    "strategy": series,
                    "benchmark": benchmark,
                },
                axis=1,
            ).dropna()

            if not aligned.empty:
                hit_rate_vs_passive = (
                    aligned["strategy"] > aligned["benchmark"]
                ).mean()

                benchmark_negative = aligned[aligned["benchmark"] < 0]

                if not benchmark_negative.empty:
                    downside_protection_rate = (
                        benchmark_negative["strategy"]
                        > benchmark_negative["benchmark"]
                    ).mean()

        rows.append(
            {
                "strategy": strategy,
                "average_stress_return": series.mean(),
                "median_stress_return": series.median(),
                "worst_stress_return": series.min(),
                "best_stress_return": series.max(),
                "hit_rate_vs_passive_in_stress": hit_rate_vs_passive,
                "downside_protection_rate": downside_protection_rate,
                "observations": len(series),
            }
        )

    return pd.DataFrame(rows).set_index("strategy")


def stress_window_interpretation(stress_summary: pd.DataFrame) -> str:
    """
    Produce a compact interpretation of the stress-window table.
    """
    if stress_summary.empty:
        return (
            "No stress-window observations were available under the current regime "
            "definition. The model needs either a longer sample or a broader stress "
            "definition before drawing stress-period conclusions."
        )

    valid_worst = stress_summary["worst_stress_return"].dropna()
    valid_avg = stress_summary["average_stress_return"].dropna()

    if valid_worst.empty or valid_avg.empty:
        return (
            "Stress-window diagnostics were generated, but the available observations "
            "are not enough to rank strategy behavior with confidence."
        )

    best_worst = str(valid_worst.idxmax())
    best_average = str(valid_avg.idxmax())

    return (
        f"Stress-window read: `{best_worst}` showed the strongest worst-period "
        f"protection during stress windows, while `{best_average}` showed the "
        "strongest average stress-period return. The portfolio question is whether "
        "the protection benefit is large enough to justify the active risk and "
        "implementation complexity."
    )


def strategy_help_hurt_diagnostics(
    strategy_returns: pd.DataFrame,
    benchmark_column: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Diagnose when each overlay helps or hurts versus passive exposure.

    This table separates active performance into:
    - periods when passive exposure is positive
    - periods when passive exposure is negative
    - periods when the overlay beats passive
    - periods when the overlay lags passive

    The goal is to explain the trade-off, not only rank strategies.
    """
    if benchmark_column not in strategy_returns.columns:
        raise KeyError(f"Benchmark column not found: {benchmark_column}")

    benchmark = strategy_returns[benchmark_column].dropna()
    rows = []

    for strategy in strategy_returns.columns:
        if strategy == benchmark_column:
            continue

        aligned = pd.concat(
            {
                "strategy": strategy_returns[strategy],
                "benchmark": benchmark,
            },
            axis=1,
        ).dropna()

        if aligned.empty:
            rows.append(
                {
                    "strategy": strategy,
                    "avg_active_return": np.nan,
                    "avg_active_when_passive_positive": np.nan,
                    "avg_active_when_passive_negative": np.nan,
                    "hit_rate_vs_passive": np.nan,
                    "missed_upside_rate": np.nan,
                    "downside_protection_rate": np.nan,
                    "best_active_period": np.nan,
                    "worst_active_period": np.nan,
                    "primary_help_zone": "insufficient_data",
                    "primary_hurt_zone": "insufficient_data",
                    "observations": 0,
                }
            )
            continue

        active = aligned["strategy"] - aligned["benchmark"]
        passive_positive = aligned[aligned["benchmark"] > 0]
        passive_negative = aligned[aligned["benchmark"] < 0]

        avg_active_positive = np.nan
        missed_upside_rate = np.nan

        if not passive_positive.empty:
            active_positive = passive_positive["strategy"] - passive_positive["benchmark"]
            avg_active_positive = active_positive.mean()
            missed_upside_rate = (
                passive_positive["strategy"] < passive_positive["benchmark"]
            ).mean()

        avg_active_negative = np.nan
        downside_protection_rate = np.nan

        if not passive_negative.empty:
            active_negative = passive_negative["strategy"] - passive_negative["benchmark"]
            avg_active_negative = active_negative.mean()
            downside_protection_rate = (
                passive_negative["strategy"] > passive_negative["benchmark"]
            ).mean()

        hit_rate = (aligned["strategy"] > aligned["benchmark"]).mean()

        primary_help_zone = "mixed"
        if not np.isnan(avg_active_negative) and avg_active_negative > 0:
            primary_help_zone = "downside_protection"
        elif not np.isnan(avg_active_positive) and avg_active_positive > 0:
            primary_help_zone = "upside_participation"
        elif active.mean() > 0:
            primary_help_zone = "broad_active_return"

        primary_hurt_zone = "mixed"
        if not np.isnan(avg_active_positive) and avg_active_positive < 0:
            primary_hurt_zone = "missed_upside"
        elif not np.isnan(avg_active_negative) and avg_active_negative < 0:
            primary_hurt_zone = "failed_protection"
        elif active.mean() < 0:
            primary_hurt_zone = "negative_active_return"

        rows.append(
            {
                "strategy": strategy,
                "avg_active_return": active.mean(),
                "avg_active_when_passive_positive": avg_active_positive,
                "avg_active_when_passive_negative": avg_active_negative,
                "hit_rate_vs_passive": hit_rate,
                "missed_upside_rate": missed_upside_rate,
                "downside_protection_rate": downside_protection_rate,
                "best_active_period": active.max(),
                "worst_active_period": active.min(),
                "primary_help_zone": primary_help_zone,
                "primary_hurt_zone": primary_hurt_zone,
                "observations": len(aligned),
            }
        )

    return pd.DataFrame(rows).set_index("strategy")


def strategy_help_hurt_interpretation(help_hurt: pd.DataFrame) -> str:
    """
    Produce a compact interpretation of the help-hurt diagnostics.
    """
    if help_hurt.empty:
        return (
            "No help-hurt diagnostics were available. The strategy table needs "
            "valid overlay and passive return series before interpretation."
        )

    valid_downside = help_hurt["downside_protection_rate"].dropna()
    valid_upside_drag = help_hurt["missed_upside_rate"].dropna()

    if valid_downside.empty:
        best_downside = "NA"
    else:
        best_downside = str(valid_downside.idxmax())

    if valid_upside_drag.empty:
        highest_upside_drag = "NA"
    else:
        highest_upside_drag = str(valid_upside_drag.idxmax())

    return (
        f"Help-hurt read: `{best_downside}` currently shows the strongest downside "
        "protection behavior versus passive exposure. "
        f"`{highest_upside_drag}` shows the highest missed-upside risk when passive "
        "Brazilian equity is positive. This is the central overlay trade-off: the "
        "portfolio can reduce left-tail pain, but protection and income strategies "
        "can also give away part of the rebound."
    )


def implementation_drag_diagnostics(
    gross_strategy_returns: pd.DataFrame,
    net_strategy_returns: pd.DataFrame,
    benchmark_column: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Separate gross overlay effect, transaction-cost drag, and net overlay effect.

    Gross returns are strategy returns before transaction costs.
    Net returns are strategy returns after transaction costs.
    The difference between the two is the implementation drag.

    This diagnostic does not yet decompose every option leg into premium income,
    payoff, and moneyness attribution. It is the intermediate institutional layer
    that shows whether the overlay survives realistic implementation costs.
    """
    if benchmark_column not in gross_strategy_returns.columns:
        raise KeyError(f"Benchmark column not found in gross returns: {benchmark_column}")

    if benchmark_column not in net_strategy_returns.columns:
        raise KeyError(f"Benchmark column not found in net returns: {benchmark_column}")

    common_index = gross_strategy_returns.index.intersection(net_strategy_returns.index)
    common_columns = gross_strategy_returns.columns.intersection(net_strategy_returns.columns)

    gross = gross_strategy_returns.loc[common_index, common_columns]
    net = net_strategy_returns.loc[common_index, common_columns]

    benchmark = net[benchmark_column]

    rows = []

    for strategy in common_columns:
        if strategy == benchmark_column:
            continue

        aligned = pd.concat(
            {
                "gross": gross[strategy],
                "net": net[strategy],
                "benchmark": benchmark,
            },
            axis=1,
        ).dropna()

        if aligned.empty:
            continue

        gross_active = aligned["gross"] - aligned["benchmark"]
        net_active = aligned["net"] - aligned["benchmark"]
        implementation_drag = aligned["net"] - aligned["gross"]

        passive_positive = aligned[aligned["benchmark"] > 0]
        passive_negative = aligned[aligned["benchmark"] < 0]

        avg_active_when_passive_positive = np.nan
        avg_active_when_passive_negative = np.nan

        if not passive_positive.empty:
            avg_active_when_passive_positive = (
                passive_positive["net"] - passive_positive["benchmark"]
            ).mean()

        if not passive_negative.empty:
            avg_active_when_passive_negative = (
                passive_negative["net"] - passive_negative["benchmark"]
            ).mean()

        avg_gross_active = gross_active.mean()
        avg_net_active = net_active.mean()
        avg_drag = implementation_drag.mean()

        drag_to_gross_signal = np.nan
        if not np.isclose(avg_gross_active, 0.0):
            drag_to_gross_signal = abs(avg_drag) / abs(avg_gross_active)

        cost_survival_ratio = np.nan
        if not np.isclose(avg_gross_active, 0.0):
            cost_survival_ratio = avg_net_active / avg_gross_active

        rows.append(
            {
                "strategy": strategy,
                "avg_gross_active_return": avg_gross_active,
                "avg_implementation_drag": avg_drag,
                "avg_net_active_return": avg_net_active,
                "total_implementation_drag": implementation_drag.sum(),
                "drag_to_gross_signal": drag_to_gross_signal,
                "cost_survival_ratio": cost_survival_ratio,
                "avg_active_when_passive_positive": avg_active_when_passive_positive,
                "avg_active_when_passive_negative": avg_active_when_passive_negative,
                "best_net_active_period": net_active.max(),
                "worst_net_active_period": net_active.min(),
                "observations": len(aligned),
            }
        )

    return pd.DataFrame(rows).set_index("strategy")


def implementation_drag_interpretation(implementation_summary: pd.DataFrame) -> str:
    """
    Produce a compact interpretation of implementation drag diagnostics.
    """
    if implementation_summary.empty:
        return (
            "No implementation-drag diagnostics were available. Gross and net "
            "strategy return tables are required before interpreting cost survival."
        )

    valid_net = implementation_summary["avg_net_active_return"].dropna()
    valid_drag_ratio = implementation_summary["drag_to_gross_signal"].dropna()

    if valid_net.empty:
        best_net = "NA"
    else:
        best_net = str(valid_net.idxmax())

    if valid_drag_ratio.empty:
        most_cost_sensitive = "NA"
    else:
        most_cost_sensitive = str(valid_drag_ratio.idxmax())

    return (
        f"Implementation read: `{best_net}` currently shows the strongest average "
        "net active return after transaction costs. "
        f"`{most_cost_sensitive}` is the most cost-sensitive overlay by drag-to-gross "
        "signal ratio. This matters because an overlay that looks useful before "
        "costs can become weak once turnover, option-leg execution, and rebalancing "
        "drag are included."
    )


def active_risk_by_regime(
    strategy_returns: pd.DataFrame,
    regime: pd.Series,
    benchmark_column: str = "passive_brazil_equity",
    periods_per_year: float = 12.0,
) -> pd.DataFrame:
    """
    Calculate active risk diagnostics by regime.

    This shows where each overlay creates tracking error versus passive exposure:
    calm markets, fragile markets, stress markets, or extreme-stress markets.

    The purpose is portfolio governance. A strategy can have attractive full-sample
    active return while creating unacceptable active risk in the wrong regime.
    """
    if benchmark_column not in strategy_returns.columns:
        raise KeyError(f"Benchmark column not found: {benchmark_column}")

    aligned_regime = align_regime_to_strategy_dates(strategy_returns, regime)

    combined = strategy_returns.copy()
    combined["regime"] = aligned_regime

    rows = []

    for regime_name, regime_data in combined.groupby("regime"):
        benchmark = regime_data[benchmark_column].dropna()

        for strategy in [col for col in regime_data.columns if col not in ["regime", benchmark_column]]:
            aligned = pd.concat(
                {
                    "strategy": regime_data[strategy],
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

            benchmark_negative = aligned[aligned["benchmark"] < 0]

            downside_hit_rate = np.nan
            if not benchmark_negative.empty:
                downside_hit_rate = (
                    benchmark_negative["strategy"] > benchmark_negative["benchmark"]
                ).mean()

            rows.append(
                {
                    "regime": regime_name,
                    "strategy": strategy,
                    "annualized_active_return": annualized_active_return,
                    "tracking_error": tracking_error,
                    "information_ratio": information_ratio,
                    "hit_rate_vs_passive": (
                        aligned["strategy"] > aligned["benchmark"]
                    ).mean(),
                    "downside_hit_rate": downside_hit_rate,
                    "avg_period_active_return": active.mean(),
                    "best_active_period": active.max(),
                    "worst_active_period": active.min(),
                    "observations": len(aligned),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "regime",
                "strategy",
                "annualized_active_return",
                "tracking_error",
                "information_ratio",
                "hit_rate_vs_passive",
                "downside_hit_rate",
                "avg_period_active_return",
                "best_active_period",
                "worst_active_period",
                "observations",
            ]
        )

    return pd.DataFrame(rows)


def active_risk_by_regime_interpretation(active_regime_summary: pd.DataFrame) -> str:
    """
    Produce a compact interpretation of active risk by regime.
    """
    if active_regime_summary.empty:
        return (
            "No active-risk-by-regime diagnostics were available. The model needs "
            "valid strategy returns and regime labels before governance conclusions "
            "can be drawn."
        )

    valid_te = active_regime_summary.dropna(subset=["tracking_error"])
    valid_ir = active_regime_summary.dropna(subset=["information_ratio"])

    if valid_te.empty:
        highest_te_strategy = "NA"
        highest_te_regime = "NA"
    else:
        highest_te_row = valid_te.loc[valid_te["tracking_error"].idxmax()]
        highest_te_strategy = str(highest_te_row["strategy"])
        highest_te_regime = str(highest_te_row["regime"])

    if valid_ir.empty:
        best_ir_strategy = "NA"
        best_ir_regime = "NA"
    else:
        best_ir_row = valid_ir.loc[valid_ir["information_ratio"].idxmax()]
        best_ir_strategy = str(best_ir_row["strategy"])
        best_ir_regime = str(best_ir_row["regime"])

    return (
        f"Active-risk-by-regime read: `{highest_te_strategy}` creates the highest "
        f"tracking error in the `{highest_te_regime}` regime. "
        f"`{best_ir_strategy}` shows the strongest information ratio in the "
        f"`{best_ir_regime}` regime. This separates a strategy that looks attractive "
        "on average from a strategy that is governable under specific market states."
    )


def benchmark_drawdown_state(
    benchmark_returns: pd.Series,
) -> pd.DataFrame:
    """
    Build benchmark drawdown states from periodic returns.

    The output classifies each period into drawdown-depth buckets and flags
    recovery windows. A recovery window is a period where the benchmark is still
    below its prior peak but is rebounding with a positive return.
    """
    returns = benchmark_returns.dropna().copy()

    cumulative = (1.0 + returns).cumprod()
    running_peak = cumulative.cummax()
    drawdown = cumulative / running_peak - 1.0

    def classify_drawdown(value: float) -> str:
        if value >= -0.02:
            return "near_peak"
        if value >= -0.05:
            return "shallow_drawdown"
        if value >= -0.10:
            return "moderate_drawdown"
        return "deep_drawdown"

    state = pd.DataFrame(
        {
            "benchmark_return": returns,
            "benchmark_cumulative": cumulative,
            "benchmark_drawdown": drawdown,
        }
    )

    state["drawdown_bucket"] = state["benchmark_drawdown"].apply(classify_drawdown)

    state["recovery_window"] = (
        (state["benchmark_return"] > 0.0)
        & (state["benchmark_drawdown"] < -0.02)
    )

    return state


def drawdown_depth_diagnostics(
    strategy_returns: pd.DataFrame,
    benchmark_column: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Evaluate strategy behavior by benchmark drawdown depth.

    This diagnostic asks whether overlays help during shallow, moderate, and
    deep drawdowns. It also shows whether the strategy creates active drag near
    market peaks.
    """
    if benchmark_column not in strategy_returns.columns:
        raise KeyError(f"Benchmark column not found: {benchmark_column}")

    state = benchmark_drawdown_state(strategy_returns[benchmark_column])

    combined = strategy_returns.join(
        state[["benchmark_return", "benchmark_drawdown", "drawdown_bucket"]],
        how="inner",
    )

    rows = []

    for bucket, bucket_data in combined.groupby("drawdown_bucket"):
        benchmark = bucket_data[benchmark_column]

        for strategy in [col for col in strategy_returns.columns if col != benchmark_column]:
            aligned = pd.concat(
                {
                    "strategy": bucket_data[strategy],
                    "benchmark": benchmark,
                },
                axis=1,
            ).dropna()

            if aligned.empty:
                continue

            active = aligned["strategy"] - aligned["benchmark"]
            benchmark_negative = aligned[aligned["benchmark"] < 0]

            downside_protection_rate = np.nan
            if not benchmark_negative.empty:
                downside_protection_rate = (
                    benchmark_negative["strategy"] > benchmark_negative["benchmark"]
                ).mean()

            rows.append(
                {
                    "drawdown_bucket": bucket,
                    "strategy": strategy,
                    "avg_strategy_return": aligned["strategy"].mean(),
                    "avg_benchmark_return": aligned["benchmark"].mean(),
                    "avg_active_return": active.mean(),
                    "hit_rate_vs_passive": (
                        aligned["strategy"] > aligned["benchmark"]
                    ).mean(),
                    "downside_protection_rate": downside_protection_rate,
                    "best_active_period": active.max(),
                    "worst_active_period": active.min(),
                    "observations": len(aligned),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "drawdown_bucket",
                "strategy",
                "avg_strategy_return",
                "avg_benchmark_return",
                "avg_active_return",
                "hit_rate_vs_passive",
                "downside_protection_rate",
                "best_active_period",
                "worst_active_period",
                "observations",
            ]
        )

    return pd.DataFrame(rows)


def recovery_window_diagnostics(
    strategy_returns: pd.DataFrame,
    benchmark_column: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Evaluate strategy behavior during benchmark recovery windows.

    Recovery windows are dangerous for hedged overlays because protection can
    become a drag when the benchmark rebounds from a drawdown.
    """
    if benchmark_column not in strategy_returns.columns:
        raise KeyError(f"Benchmark column not found: {benchmark_column}")

    state = benchmark_drawdown_state(strategy_returns[benchmark_column])
    recovery_dates = state[state["recovery_window"]].index

    recovery_data = strategy_returns.loc[
        strategy_returns.index.intersection(recovery_dates)
    ]

    rows = []

    if recovery_data.empty:
        return pd.DataFrame(
            columns=[
                "strategy",
                "avg_strategy_return",
                "avg_benchmark_return",
                "avg_active_return_in_recovery",
                "hit_rate_vs_passive_in_recovery",
                "missed_recovery_rate",
                "best_active_recovery_period",
                "worst_active_recovery_period",
                "observations",
            ]
        )

    benchmark = recovery_data[benchmark_column]

    for strategy in [col for col in strategy_returns.columns if col != benchmark_column]:
        aligned = pd.concat(
            {
                "strategy": recovery_data[strategy],
                "benchmark": benchmark,
            },
            axis=1,
        ).dropna()

        if aligned.empty:
            continue

        active = aligned["strategy"] - aligned["benchmark"]

        rows.append(
            {
                "strategy": strategy,
                "avg_strategy_return": aligned["strategy"].mean(),
                "avg_benchmark_return": aligned["benchmark"].mean(),
                "avg_active_return_in_recovery": active.mean(),
                "hit_rate_vs_passive_in_recovery": (
                    aligned["strategy"] > aligned["benchmark"]
                ).mean(),
                "missed_recovery_rate": (
                    aligned["strategy"] < aligned["benchmark"]
                ).mean(),
                "best_active_recovery_period": active.max(),
                "worst_active_recovery_period": active.min(),
                "observations": len(aligned),
            }
        )

    return pd.DataFrame(rows).set_index("strategy")


def drawdown_recovery_interpretation(
    drawdown_summary: pd.DataFrame,
    recovery_summary: pd.DataFrame,
) -> str:
    """
    Produce a compact interpretation of drawdown-depth and recovery-window behavior.
    """
    if drawdown_summary.empty and recovery_summary.empty:
        return (
            "No drawdown-depth or recovery-window diagnostics were available. "
            "The strategy return table needs valid benchmark and overlay returns "
            "before this layer can be interpreted."
        )

    deep = drawdown_summary[
        drawdown_summary["drawdown_bucket"] == "deep_drawdown"
    ] if not drawdown_summary.empty else pd.DataFrame()

    if deep.empty:
        best_deep = "NA"
    else:
        valid_deep = deep.dropna(subset=["avg_active_return"])
        best_deep = (
            "NA"
            if valid_deep.empty
            else str(valid_deep.loc[valid_deep["avg_active_return"].idxmax(), "strategy"])
        )

    if recovery_summary.empty:
        highest_recovery_drag = "NA"
    else:
        valid_recovery = recovery_summary.dropna(
            subset=["avg_active_return_in_recovery"]
        )

        highest_recovery_drag = (
            "NA"
            if valid_recovery.empty
            else str(
                valid_recovery.loc[
                    valid_recovery["avg_active_return_in_recovery"].idxmin()
                ].name
            )
        )

    return (
        f"Drawdown-recovery read: `{best_deep}` shows the strongest average active "
        "behavior during deep benchmark drawdowns. "
        f"`{highest_recovery_drag}` shows the largest active drag during recovery "
        "windows. This is the key hedge-governance trade-off: protection can help "
        "during the fall, but it must not destroy too much of the rebound."
    )


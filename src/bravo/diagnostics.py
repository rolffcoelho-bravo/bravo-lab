"""
Diagnostics layer for BRAVO Lab.

This module contains portfolio-governance diagnostics for Brazilian equity
overlay research, including:

- regime-level performance
- stress-window performance
- help-hurt diagnostics
- implementation-drag diagnostics
- active risk by regime
- drawdown-depth diagnostics
- recovery-window diagnostics
- model-implied option overlay attribution

The option attribution layer is synthetic and model-implied. It does not claim
to represent actual traded B3 option-chain prices.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def align_regime_to_strategy_dates(
    strategy_returns: pd.DataFrame,
    regime: pd.Series,
) -> pd.Series:
    """
    Align daily regime labels to periodic strategy return dates.
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

    return pd.DataFrame(rows)


def stress_window_summary(
    strategy_returns: pd.DataFrame,
    regime: pd.Series,
    stress_regimes: tuple[str, ...] = ("stress", "extreme_stress"),
    benchmark_column: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Evaluate strategy behavior only during stress regimes.
    """
    aligned_regime = align_regime_to_strategy_dates(strategy_returns, regime)

    combined = strategy_returns.copy()
    combined["regime"] = aligned_regime

    stress_data = combined[combined["regime"].isin(stress_regimes)].dropna()

    if stress_data.empty:
        return pd.DataFrame()

    benchmark = stress_data[benchmark_column]
    rows = []

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
            continue

        active = aligned["strategy"] - aligned["benchmark"]

        passive_positive = aligned[aligned["benchmark"] > 0]
        passive_negative = aligned[aligned["benchmark"] < 0]

        avg_active_positive = np.nan
        missed_upside_rate = np.nan

        if not passive_positive.empty:
            active_positive = (
                passive_positive["strategy"] - passive_positive["benchmark"]
            )
            avg_active_positive = active_positive.mean()
            missed_upside_rate = (
                passive_positive["strategy"] < passive_positive["benchmark"]
            ).mean()

        avg_active_negative = np.nan
        downside_protection_rate = np.nan

        if not passive_negative.empty:
            active_negative = (
                passive_negative["strategy"] - passive_negative["benchmark"]
            )
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

    best_downside = "NA" if valid_downside.empty else str(valid_downside.idxmax())
    highest_upside_drag = (
        "NA" if valid_upside_drag.empty else str(valid_upside_drag.idxmax())
    )

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

    best_net = "NA" if valid_net.empty else str(valid_net.idxmax())
    most_cost_sensitive = (
        "NA" if valid_drag_ratio.empty else str(valid_drag_ratio.idxmax())
    )

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
    """
    if benchmark_column not in strategy_returns.columns:
        raise KeyError(f"Benchmark column not found: {benchmark_column}")

    aligned_regime = align_regime_to_strategy_dates(strategy_returns, regime)

    combined = strategy_returns.copy()
    combined["regime"] = aligned_regime

    rows = []

    for regime_name, regime_data in combined.groupby("regime"):
        benchmark = regime_data[benchmark_column].dropna()

        for strategy in [
            col for col in regime_data.columns if col not in ["regime", benchmark_column]
        ]:
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

    return pd.DataFrame(rows)


def recovery_window_diagnostics(
    strategy_returns: pd.DataFrame,
    benchmark_column: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Evaluate strategy behavior during benchmark recovery windows.
    """
    if benchmark_column not in strategy_returns.columns:
        raise KeyError(f"Benchmark column not found: {benchmark_column}")

    state = benchmark_drawdown_state(strategy_returns[benchmark_column])
    recovery_dates = state[state["recovery_window"]].index

    recovery_data = strategy_returns.loc[
        strategy_returns.index.intersection(recovery_dates)
    ]

    if recovery_data.empty:
        return pd.DataFrame()

    benchmark = recovery_data[benchmark_column]
    rows = []

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

    deep = (
        drawdown_summary[drawdown_summary["drawdown_bucket"] == "deep_drawdown"]
        if not drawdown_summary.empty
        else pd.DataFrame()
    )

    if deep.empty:
        best_deep = "NA"
    else:
        valid_deep = deep.dropna(subset=["avg_active_return"])
        best_deep = (
            "NA"
            if valid_deep.empty
            else str(
                valid_deep.loc[
                    valid_deep["avg_active_return"].idxmax(),
                    "strategy",
                ]
            )
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


def _option_attr_normal_cdf(x: float) -> float:
    """
    Standard normal cumulative distribution function.
    """
    from math import erf, sqrt

    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _option_attr_black_scholes_price(
    spot: float,
    strike: float,
    maturity_years: float,
    annualized_volatility: float,
    risk_free_rate_annual: float = 0.0,
    option_type: str = "call",
) -> float:
    """
    Minimal Black-Scholes option price used for attribution diagnostics.

    This is intentionally local, dependency-light, and transparent. It is used
    only to create model-implied option attribution for the synthetic overlay
    engine. It does not claim to represent actual traded B3 option-chain prices.
    """
    from math import exp, log, sqrt

    if spot <= 0 or strike <= 0:
        return np.nan

    if maturity_years <= 0 or annualized_volatility <= 0:
        if option_type == "call":
            return max(spot - strike, 0.0)
        if option_type == "put":
            return max(strike - spot, 0.0)
        raise ValueError(f"Unknown option type: {option_type}")

    d1 = (
        log(spot / strike)
        + (risk_free_rate_annual + 0.5 * annualized_volatility**2) * maturity_years
    ) / (annualized_volatility * sqrt(maturity_years))

    d2 = d1 - annualized_volatility * sqrt(maturity_years)

    if option_type == "call":
        return (
            spot * _option_attr_normal_cdf(d1)
            - strike
            * exp(-risk_free_rate_annual * maturity_years)
            * _option_attr_normal_cdf(d2)
        )

    if option_type == "put":
        return (
            strike
            * exp(-risk_free_rate_annual * maturity_years)
            * _option_attr_normal_cdf(-d2)
            - spot * _option_attr_normal_cdf(-d1)
        )

    raise ValueError(f"Unknown option type: {option_type}")


def _option_attr_regime_at_date(
    regime: pd.Series | None,
    date: pd.Timestamp,
) -> str:
    """
    Get the most recent regime available at a rebalance date.
    """
    if regime is None or regime.empty:
        return "neutral"

    clean_regime = regime.dropna().sort_index()
    available = clean_regime.loc[clean_regime.index <= date]

    if available.empty:
        return "neutral"

    return str(available.iloc[-1])


def _option_attr_strategy_for_regime(regime_name: str) -> str:
    """
    Map regime labels to the stress-aware overlay decision rule.
    """
    if regime_name == "calm":
        return "passive_brazil_equity"

    if regime_name == "fragile":
        return "covered_call"

    if regime_name in {"stress", "extreme_stress"}:
        return "collar"

    return "passive_brazil_equity"


def option_overlay_attribution(
    prices: pd.Series,
    returns: pd.Series,
    regime: pd.Series | None = None,
    maturity_days: int = 21,
    transaction_cost_bps: float = 5.0,
    call_moneyness: float = 1.03,
    put_moneyness: float = 0.97,
    volatility_window: int = 63,
    trading_days_per_year: int = 252,
    risk_free_rate_annual: float = 0.0,
) -> pd.DataFrame:
    """
    Build model-implied attribution for synthetic option overlays.
    """
    clean_prices = prices.dropna().sort_index()
    clean_returns = returns.dropna().sort_index()

    if clean_prices.empty or len(clean_prices) <= maturity_days:
        return pd.DataFrame()

    global_volatility = clean_returns.std(ddof=1) * np.sqrt(trading_days_per_year)

    if np.isnan(global_volatility) or global_volatility <= 0:
        global_volatility = 0.25

    rows = []

    for start_position in range(0, len(clean_prices) - maturity_days, maturity_days):
        end_position = start_position + maturity_days

        start_date = clean_prices.index[start_position]
        end_date = clean_prices.index[end_position]

        start_price = float(clean_prices.iloc[start_position])
        end_price = float(clean_prices.iloc[end_position])

        if start_price <= 0:
            continue

        underlying_return = end_price / start_price - 1.0

        volatility_sample = clean_returns.loc[
            clean_returns.index <= start_date
        ].tail(volatility_window)

        annualized_volatility = volatility_sample.std(ddof=1) * np.sqrt(
            trading_days_per_year
        )

        if np.isnan(annualized_volatility) or annualized_volatility <= 0:
            annualized_volatility = global_volatility

        maturity_years = maturity_days / trading_days_per_year

        call_strike = start_price * call_moneyness
        put_strike = start_price * put_moneyness

        call_premium = _option_attr_black_scholes_price(
            spot=start_price,
            strike=call_strike,
            maturity_years=maturity_years,
            annualized_volatility=annualized_volatility,
            risk_free_rate_annual=risk_free_rate_annual,
            option_type="call",
        )

        put_premium = _option_attr_black_scholes_price(
            spot=start_price,
            strike=put_strike,
            maturity_years=maturity_years,
            annualized_volatility=annualized_volatility,
            risk_free_rate_annual=risk_free_rate_annual,
            option_type="put",
        )

        call_premium_fraction = call_premium / start_price
        put_premium_fraction = put_premium / start_price

        call_payoff_fraction = max(end_price - call_strike, 0.0) / start_price
        put_payoff_fraction = max(put_strike - end_price, 0.0) / start_price

        one_leg_cost = transaction_cost_bps / 10000.0
        two_leg_cost = 2.0 * one_leg_cost

        regime_name = _option_attr_regime_at_date(regime, start_date)
        stress_strategy = _option_attr_strategy_for_regime(regime_name)

        period_specs = [
            {
                "strategy": "covered_call",
                "selected_component": "covered_call",
                "option_legs": 1,
                "premium_income": call_premium_fraction,
                "protection_cost": 0.0,
                "payoff_effect": -call_payoff_fraction,
                "implementation_drag": -one_leg_cost,
            },
            {
                "strategy": "collar",
                "selected_component": "collar",
                "option_legs": 2,
                "premium_income": call_premium_fraction,
                "protection_cost": -put_premium_fraction,
                "payoff_effect": put_payoff_fraction - call_payoff_fraction,
                "implementation_drag": -two_leg_cost,
            },
        ]

        if stress_strategy == "covered_call":
            stress_spec = period_specs[0].copy()
        elif stress_strategy == "collar":
            stress_spec = period_specs[1].copy()
        else:
            stress_spec = {
                "strategy": "stress_aware_overlay",
                "selected_component": "passive_brazil_equity",
                "option_legs": 0,
                "premium_income": 0.0,
                "protection_cost": 0.0,
                "payoff_effect": 0.0,
                "implementation_drag": 0.0,
            }

        stress_spec["strategy"] = "stress_aware_overlay"
        period_specs.append(stress_spec)

        for spec in period_specs:
            gross_overlay_effect = (
                spec["premium_income"]
                + spec["protection_cost"]
                + spec["payoff_effect"]
            )

            net_overlay_effect = gross_overlay_effect + spec["implementation_drag"]
            net_strategy_return = underlying_return + net_overlay_effect

            rows.append(
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "strategy": spec["strategy"],
                    "selected_component": spec["selected_component"],
                    "regime": regime_name,
                    "start_price": start_price,
                    "end_price": end_price,
                    "underlying_return": underlying_return,
                    "annualized_volatility": annualized_volatility,
                    "call_premium_income": spec["premium_income"],
                    "put_protection_cost": spec["protection_cost"],
                    "option_payoff_effect": spec["payoff_effect"],
                    "implementation_drag": spec["implementation_drag"],
                    "gross_overlay_effect": gross_overlay_effect,
                    "net_overlay_effect": net_overlay_effect,
                    "net_strategy_return": net_strategy_return,
                    "option_legs": spec["option_legs"],
                }
            )

    return pd.DataFrame(rows)


def option_overlay_attribution_summary(
    attribution: pd.DataFrame,
) -> pd.DataFrame:
    """
    Summarize model-implied option attribution by strategy.
    """
    if attribution.empty:
        return pd.DataFrame()

    rows = []

    for strategy, data in attribution.groupby("strategy"):
        rows.append(
            {
                "strategy": strategy,
                "avg_underlying_return": data["underlying_return"].mean(),
                "avg_call_premium_income": data["call_premium_income"].mean(),
                "avg_put_protection_cost": data["put_protection_cost"].mean(),
                "avg_option_payoff_effect": data["option_payoff_effect"].mean(),
                "avg_implementation_drag": data["implementation_drag"].mean(),
                "avg_gross_overlay_effect": data["gross_overlay_effect"].mean(),
                "avg_net_overlay_effect": data["net_overlay_effect"].mean(),
                "avg_net_strategy_return": data["net_strategy_return"].mean(),
                "positive_net_overlay_rate": (data["net_overlay_effect"] > 0).mean(),
                "observations": len(data),
            }
        )

    return pd.DataFrame(rows).set_index("strategy")


def option_overlay_attribution_interpretation(summary: pd.DataFrame) -> str:
    """
    Produce a compact interpretation of model-implied option attribution.
    """
    if summary.empty:
        return (
            "No option-attribution diagnostics were available. The attribution layer "
            "requires valid prices, returns, and synthetic overlay assumptions."
        )

    valid_net = summary["avg_net_overlay_effect"].dropna()
    valid_premium = summary["avg_call_premium_income"].dropna()
    valid_payoff = summary["avg_option_payoff_effect"].dropna()

    best_net = "NA" if valid_net.empty else str(valid_net.idxmax())
    largest_premium = "NA" if valid_premium.empty else str(valid_premium.idxmax())
    strongest_payoff = "NA" if valid_payoff.empty else str(valid_payoff.idxmax())

    return (
        f"Option-attribution read: `{best_net}` currently shows the strongest "
        "average net overlay effect after model-implied premium, payoff, protection "
        "cost, and implementation drag. "
        f"`{largest_premium}` generates the largest average call-premium income. "
        f"`{strongest_payoff}` has the strongest average payoff contribution. "
        "This is still synthetic attribution, not real B3 option-chain attribution, "
        "but it makes the overlay engine explain why the strategy works or fails."
    )


def option_attribution_by_regime(
    attribution: pd.DataFrame,
) -> pd.DataFrame:
    """
    Summarize model-implied option attribution by regime and strategy.

    This shows whether premium income, payoff effect, protection cost,
    implementation drag, and net overlay effect behave differently across
    calm, fragile, stress, and extreme-stress regimes.
    """
    if attribution.empty:
        return pd.DataFrame()

    rows = []

    for (regime_name, strategy), data in attribution.groupby(["regime", "strategy"]):
        rows.append(
            {
                "regime": regime_name,
                "strategy": strategy,
                "avg_underlying_return": data["underlying_return"].mean(),
                "avg_call_premium_income": data["call_premium_income"].mean(),
                "avg_put_protection_cost": data["put_protection_cost"].mean(),
                "avg_option_payoff_effect": data["option_payoff_effect"].mean(),
                "avg_implementation_drag": data["implementation_drag"].mean(),
                "avg_gross_overlay_effect": data["gross_overlay_effect"].mean(),
                "avg_net_overlay_effect": data["net_overlay_effect"].mean(),
                "avg_net_strategy_return": data["net_strategy_return"].mean(),
                "positive_net_overlay_rate": (data["net_overlay_effect"] > 0).mean(),
                "observations": len(data),
            }
        )

    return pd.DataFrame(rows)


def _option_attr_drawdown_bucket_at_date(
    drawdown_state: pd.DataFrame,
    date: pd.Timestamp,
) -> str:
    """
    Get the most recent benchmark drawdown bucket available at a date.
    """
    if drawdown_state.empty:
        return "unknown"

    state = drawdown_state.dropna(subset=["drawdown_bucket"]).sort_index()
    available = state.loc[state.index <= date]

    if available.empty:
        return "unknown"

    return str(available["drawdown_bucket"].iloc[-1])


def option_attribution_by_drawdown_bucket(
    attribution: pd.DataFrame,
    benchmark_returns: pd.Series,
) -> pd.DataFrame:
    """
    Summarize model-implied option attribution by benchmark drawdown bucket.

    This shows whether option components behave differently near peaks, during
    shallow drawdowns, moderate drawdowns, and deep drawdowns.
    """
    if attribution.empty:
        return pd.DataFrame()

    drawdown_state = benchmark_drawdown_state(benchmark_returns)

    enriched = attribution.copy()
    enriched["end_date"] = pd.to_datetime(enriched["end_date"])

    enriched["drawdown_bucket"] = enriched["end_date"].apply(
        lambda date: _option_attr_drawdown_bucket_at_date(drawdown_state, date)
    )

    rows = []

    for (bucket, strategy), data in enriched.groupby(["drawdown_bucket", "strategy"]):
        rows.append(
            {
                "drawdown_bucket": bucket,
                "strategy": strategy,
                "avg_underlying_return": data["underlying_return"].mean(),
                "avg_call_premium_income": data["call_premium_income"].mean(),
                "avg_put_protection_cost": data["put_protection_cost"].mean(),
                "avg_option_payoff_effect": data["option_payoff_effect"].mean(),
                "avg_implementation_drag": data["implementation_drag"].mean(),
                "avg_gross_overlay_effect": data["gross_overlay_effect"].mean(),
                "avg_net_overlay_effect": data["net_overlay_effect"].mean(),
                "avg_net_strategy_return": data["net_strategy_return"].mean(),
                "positive_net_overlay_rate": (data["net_overlay_effect"] > 0).mean(),
                "observations": len(data),
            }
        )

    return pd.DataFrame(rows)


def option_attribution_context_interpretation(
    regime_summary: pd.DataFrame,
    drawdown_summary: pd.DataFrame,
) -> str:
    """
    Produce a compact interpretation of option attribution by regime and drawdown bucket.
    """
    if regime_summary.empty and drawdown_summary.empty:
        return (
            "No option-attribution context diagnostics were available. The model "
            "needs valid option attribution, regime labels, and benchmark drawdown "
            "states before this layer can be interpreted."
        )

    stress_best = "NA"
    calm_premium = "NA"
    deep_payoff = "NA"
    near_peak_drag = "NA"

    if not regime_summary.empty:
        stress_rows = regime_summary[
            regime_summary["regime"].isin(["stress", "extreme_stress"])
        ].dropna(subset=["avg_net_overlay_effect"])

        if not stress_rows.empty:
            stress_best = str(
                stress_rows.loc[
                    stress_rows["avg_net_overlay_effect"].idxmax(),
                    "strategy",
                ]
            )

        calm_rows = regime_summary[
            regime_summary["regime"] == "calm"
        ].dropna(subset=["avg_call_premium_income"])

        if not calm_rows.empty:
            calm_premium = str(
                calm_rows.loc[
                    calm_rows["avg_call_premium_income"].idxmax(),
                    "strategy",
                ]
            )

    if not drawdown_summary.empty:
        deep_rows = drawdown_summary[
            drawdown_summary["drawdown_bucket"] == "deep_drawdown"
        ].dropna(subset=["avg_option_payoff_effect"])

        if not deep_rows.empty:
            deep_payoff = str(
                deep_rows.loc[
                    deep_rows["avg_option_payoff_effect"].idxmax(),
                    "strategy",
                ]
            )

        near_peak_rows = drawdown_summary[
            drawdown_summary["drawdown_bucket"] == "near_peak"
        ].dropna(subset=["avg_net_overlay_effect"])

        if not near_peak_rows.empty:
            near_peak_drag = str(
                near_peak_rows.loc[
                    near_peak_rows["avg_net_overlay_effect"].idxmin(),
                    "strategy",
                ]
            )

    return (
        f"Option-context read: `{stress_best}` shows the strongest net overlay "
        "effect during stress regimes. "
        f"`{calm_premium}` generates the strongest call-premium income in calm "
        "regimes. "
        f"`{deep_payoff}` shows the strongest payoff contribution during deep "
        "drawdown buckets. "
        f"`{near_peak_drag}` shows the weakest net overlay effect near benchmark "
        "peaks. This separates income, protection, payoff, and drag across the "
        "market states where portfolio committees actually make allocation decisions."
    )


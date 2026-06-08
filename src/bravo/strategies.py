"""
Derivative overlay strategy prototypes for BRAVO Lab.

This module implements synthetic passive, covered call, collar, and
stress-aware overlay strategies.

The implementation is intentionally transparent:
- monthly rebalancing approximation
- Black-Scholes synthetic option premiums
- configurable transaction-cost assumption
- regime-dependent strategy switching
- no real B3 option-chain data yet
- no tax assumptions
- no liquidity constraints

The goal is to create a working research baseline before adding market
microstructure realism.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from bravo.config import TRADING_DAYS_PER_YEAR
from bravo.options import (
    black_scholes_call_price,
    black_scholes_put_price,
    estimate_annualized_volatility,
    option_premium_fraction,
)


@dataclass
class OverlayBacktestResult:
    """
    Container for strategy return series and diagnostics.
    """

    returns: pd.DataFrame
    diagnostics: pd.DataFrame


def _rebalance_points(index: pd.Index, step: int) -> list[int]:
    """
    Create integer rebalance points for a fixed-step approximation.
    """
    if len(index) == 0:
        return []

    points = list(range(0, len(index), step))

    if points[-1] != len(index) - 1:
        points.append(len(index) - 1)

    return points


def _transaction_cost_fraction(
    transaction_cost_bps: float,
    number_of_legs: int,
) -> float:
    """
    Convert transaction-cost assumption into a return drag.

    Parameters
    ----------
    transaction_cost_bps:
        Cost in basis points per option leg.
    number_of_legs:
        Number of option legs traded during the rebalance.

    Returns
    -------
    float
        Cost as a fraction of portfolio value.
    """
    return (transaction_cost_bps / 10_000) * number_of_legs


def _get_regime_at_date(regime: pd.Series, date: pd.Timestamp) -> str:
    """
    Get the most recent regime available at or before a given date.
    """
    if regime is None or regime.empty:
        return "neutral"

    available = regime.loc[regime.index <= date].dropna()

    if available.empty:
        return "neutral"

    return str(available.iloc[-1])


def _strategy_for_regime(regime_value: str) -> str:
    """
    Map regime state into strategy selection.

    The mapping is deliberately conservative:
    - calm: passive exposure
    - fragile: covered call income
    - stress: collar protection
    - extreme stress: collar protection
    - neutral or unknown: passive exposure
    """
    regime_value = str(regime_value).lower()

    if regime_value == "calm":
        return "passive_brazil_equity"

    if regime_value == "fragile":
        return "covered_call"

    if regime_value in {"stress", "extreme_stress"}:
        return "collar"

    return "passive_brazil_equity"


def build_passive_returns(
    asset_returns: pd.Series,
    name: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Create passive benchmark daily returns.
    """
    return asset_returns.dropna().rename(name).to_frame()


def build_passive_period_returns(
    prices: pd.Series,
    rebalance_index: pd.Index,
    name: str = "passive_brazil_equity",
) -> pd.Series:
    """
    Create passive benchmark returns on the same rebalance dates as overlays.
    """
    period_prices = prices.loc[rebalance_index].dropna()
    return period_prices.pct_change().rename(name)


def covered_call_overlay_returns(
    prices: pd.Series,
    returns: pd.Series,
    call_moneyness: float = 1.03,
    maturity_days: int = 21,
    volatility_window: int = 63,
    risk_free_rate: float = 0.0,
    transaction_cost_bps: float = 5.0,
) -> OverlayBacktestResult:
    """
    Backtest a synthetic covered call overlay.

    The strategy owns the underlying and sells an out-of-the-money call at each
    rebalance date. The payoff is evaluated at the next rebalance date.

    The transaction-cost assumption is applied as a simple return drag per
    option leg. A covered call has one option leg.
    """
    aligned = pd.concat({"price": prices, "return": returns}, axis=1).dropna()
    vol = estimate_annualized_volatility(aligned["return"], window=volatility_window)

    rebalance_points = _rebalance_points(aligned.index, maturity_days)

    strategy_returns = []
    diagnostics = []

    time_to_maturity = maturity_days / TRADING_DAYS_PER_YEAR
    cost_fraction = _transaction_cost_fraction(
        transaction_cost_bps=transaction_cost_bps,
        number_of_legs=1,
    )

    for start_pos, end_pos in zip(rebalance_points[:-1], rebalance_points[1:]):
        start_date = aligned.index[start_pos]
        end_date = aligned.index[end_pos]

        spot_start = float(aligned["price"].iloc[start_pos])
        spot_end = float(aligned["price"].iloc[end_pos])
        volatility = float(vol.iloc[start_pos])

        if np.isnan(volatility):
            continue

        strike = spot_start * call_moneyness

        call_price = black_scholes_call_price(
            spot=spot_start,
            strike=strike,
            time_to_maturity_years=time_to_maturity,
            volatility=volatility,
            risk_free_rate=risk_free_rate,
        )

        premium_fraction = option_premium_fraction(call_price, spot_start)

        underlying_period_return = spot_end / spot_start - 1
        call_payoff_fraction = max(spot_end / spot_start - call_moneyness, 0)

        overlay_period_return = (
            underlying_period_return
            + premium_fraction
            - call_payoff_fraction
            - cost_fraction
        )

        strategy_returns.append(
            {
                "date": end_date,
                "covered_call": overlay_period_return,
            }
        )

        diagnostics.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "spot_start": spot_start,
                "spot_end": spot_end,
                "strike_call": strike,
                "estimated_volatility": volatility,
                "call_premium_fraction": premium_fraction,
                "transaction_cost_fraction": cost_fraction,
                "underlying_period_return": underlying_period_return,
                "covered_call_period_return": overlay_period_return,
            }
        )

    returns_df = pd.DataFrame(strategy_returns).set_index("date")
    diagnostics_df = pd.DataFrame(diagnostics)

    return OverlayBacktestResult(returns=returns_df, diagnostics=diagnostics_df)


def collar_overlay_returns(
    prices: pd.Series,
    returns: pd.Series,
    put_moneyness: float = 0.95,
    call_moneyness: float = 1.03,
    maturity_days: int = 21,
    volatility_window: int = 63,
    risk_free_rate: float = 0.0,
    transaction_cost_bps: float = 5.0,
) -> OverlayBacktestResult:
    """
    Backtest a synthetic protective collar overlay.

    The strategy owns the underlying, buys an out-of-the-money put, and sells
    an out-of-the-money call at each rebalance date.

    The transaction-cost assumption is applied as a simple return drag per
    option leg. A collar has two option legs.
    """
    aligned = pd.concat({"price": prices, "return": returns}, axis=1).dropna()
    vol = estimate_annualized_volatility(aligned["return"], window=volatility_window)

    rebalance_points = _rebalance_points(aligned.index, maturity_days)

    strategy_returns = []
    diagnostics = []

    time_to_maturity = maturity_days / TRADING_DAYS_PER_YEAR
    cost_fraction = _transaction_cost_fraction(
        transaction_cost_bps=transaction_cost_bps,
        number_of_legs=2,
    )

    for start_pos, end_pos in zip(rebalance_points[:-1], rebalance_points[1:]):
        start_date = aligned.index[start_pos]
        end_date = aligned.index[end_pos]

        spot_start = float(aligned["price"].iloc[start_pos])
        spot_end = float(aligned["price"].iloc[end_pos])
        volatility = float(vol.iloc[start_pos])

        if np.isnan(volatility):
            continue

        put_strike = spot_start * put_moneyness
        call_strike = spot_start * call_moneyness

        put_price = black_scholes_put_price(
            spot=spot_start,
            strike=put_strike,
            time_to_maturity_years=time_to_maturity,
            volatility=volatility,
            risk_free_rate=risk_free_rate,
        )

        call_price = black_scholes_call_price(
            spot=spot_start,
            strike=call_strike,
            time_to_maturity_years=time_to_maturity,
            volatility=volatility,
            risk_free_rate=risk_free_rate,
        )

        put_cost_fraction = option_premium_fraction(put_price, spot_start)
        call_premium_fraction = option_premium_fraction(call_price, spot_start)
        net_premium_fraction = call_premium_fraction - put_cost_fraction

        underlying_period_return = spot_end / spot_start - 1

        put_payoff_fraction = max(put_moneyness - spot_end / spot_start, 0)
        call_payoff_fraction = max(spot_end / spot_start - call_moneyness, 0)

        collar_period_return = (
            underlying_period_return
            + put_payoff_fraction
            - call_payoff_fraction
            + net_premium_fraction
            - cost_fraction
        )

        strategy_returns.append(
            {
                "date": end_date,
                "collar": collar_period_return,
            }
        )

        diagnostics.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "spot_start": spot_start,
                "spot_end": spot_end,
                "strike_put": put_strike,
                "strike_call": call_strike,
                "estimated_volatility": volatility,
                "put_cost_fraction": put_cost_fraction,
                "call_premium_fraction": call_premium_fraction,
                "net_premium_fraction": net_premium_fraction,
                "transaction_cost_fraction": cost_fraction,
                "underlying_period_return": underlying_period_return,
                "collar_period_return": collar_period_return,
            }
        )

    returns_df = pd.DataFrame(strategy_returns).set_index("date")
    diagnostics_df = pd.DataFrame(diagnostics)

    return OverlayBacktestResult(returns=returns_df, diagnostics=diagnostics_df)


def stress_aware_overlay_returns(
    overlay_returns: pd.DataFrame,
    covered_call_diagnostics: pd.DataFrame,
    regime: pd.Series,
) -> OverlayBacktestResult:
    """
    Build a stress-aware overlay using regime-dependent switching.

    The strategy selection is made at the beginning of each holding period using
    the most recent available regime signal.

    Mapping:
    - calm: passive exposure
    - fragile: covered call
    - stress: collar
    - extreme_stress: collar
    - neutral: passive exposure
    """
    strategy_returns = []
    diagnostics = []

    if overlay_returns.empty:
        return OverlayBacktestResult(
            returns=pd.DataFrame(columns=["stress_aware_overlay"]),
            diagnostics=pd.DataFrame(),
        )

    diagnostics_by_end = covered_call_diagnostics.set_index("end_date")

    for date, row in overlay_returns.iterrows():
        if date not in diagnostics_by_end.index:
            continue

        start_date = diagnostics_by_end.loc[date, "start_date"]
        regime_value = _get_regime_at_date(regime=regime, date=start_date)
        selected_strategy = _strategy_for_regime(regime_value)

        selected_return = row.get(selected_strategy, np.nan)

        strategy_returns.append(
            {
                "date": date,
                "stress_aware_overlay": selected_return,
            }
        )

        diagnostics.append(
            {
                "start_date": start_date,
                "end_date": date,
                "regime": regime_value,
                "selected_strategy": selected_strategy,
                "period_return": selected_return,
            }
        )

    returns_df = pd.DataFrame(strategy_returns).set_index("date")
    diagnostics_df = pd.DataFrame(diagnostics)

    return OverlayBacktestResult(returns=returns_df, diagnostics=diagnostics_df)


def build_overlay_return_table(
    prices: pd.Series,
    returns: pd.Series,
    regime: Optional[pd.Series] = None,
    maturity_days: int = 21,
    transaction_cost_bps: float = 5.0,
) -> pd.DataFrame:
    """
    Build a comparison table with passive, covered call, collar, and optional
    stress-aware overlay returns.

    Returns are evaluated on the same rebalance dates to make comparison fair.
    """
    covered_call = covered_call_overlay_returns(
        prices=prices,
        returns=returns,
        maturity_days=maturity_days,
        transaction_cost_bps=transaction_cost_bps,
    )

    collar = collar_overlay_returns(
        prices=prices,
        returns=returns,
        maturity_days=maturity_days,
        transaction_cost_bps=transaction_cost_bps,
    )

    rebalance_index = covered_call.returns.index.intersection(collar.returns.index)

    passive_period_returns = build_passive_period_returns(
        prices=prices,
        rebalance_index=rebalance_index,
        name="passive_brazil_equity",
    )

    overlay_table = pd.concat(
        [
            passive_period_returns,
            covered_call.returns.loc[rebalance_index, "covered_call"],
            collar.returns.loc[rebalance_index, "collar"],
        ],
        axis=1,
    ).dropna()

    if regime is not None:
        stress_aware = stress_aware_overlay_returns(
            overlay_returns=overlay_table,
            covered_call_diagnostics=covered_call.diagnostics,
            regime=regime,
        )

        overlay_table = pd.concat(
            [
                overlay_table,
                stress_aware.returns["stress_aware_overlay"],
            ],
            axis=1,
        ).dropna()

    return overlay_table
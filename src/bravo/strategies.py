"""
Derivative overlay strategy prototypes for BRAVO Lab.

This module implements the first synthetic covered call and collar overlays.

The first implementation is intentionally simple and auditable:
- monthly rebalancing approximation
- Black-Scholes synthetic option premiums
- no real B3 option-chain data yet
- no transaction costs yet
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
    points = list(range(0, len(index), step))

    if points[-1] != len(index) - 1:
        points.append(len(index) - 1)

    return points


def build_passive_returns(
    asset_returns: pd.Series,
    name: str = "passive_brazil_equity",
) -> pd.DataFrame:
    """
    Create passive benchmark returns.
    """
    return asset_returns.dropna().rename(name).to_frame()


def covered_call_overlay_returns(
    prices: pd.Series,
    returns: pd.Series,
    call_moneyness: float = 1.03,
    maturity_days: int = 21,
    volatility_window: int = 63,
    risk_free_rate: float = 0.0,
) -> OverlayBacktestResult:
    """
    Backtest a synthetic covered call overlay.

    The strategy owns the underlying and sells an out-of-the-money call at each
    rebalance date. The payoff is evaluated at the next rebalance date.

    Parameters
    ----------
    prices:
        Adjusted price series for the underlying.
    returns:
        Daily return series for the underlying.
    call_moneyness:
        Call strike as a multiple of spot. Example: 1.03 means 3% OTM.
    maturity_days:
        Approximate option maturity in trading days.
    volatility_window:
        Rolling window used to estimate annualized volatility.
    risk_free_rate:
        Annual risk-free rate used in Black-Scholes.
    """
    aligned = pd.concat({"price": prices, "return": returns}, axis=1).dropna()
    vol = estimate_annualized_volatility(aligned["return"], window=volatility_window)

    rebalance_points = _rebalance_points(aligned.index, maturity_days)

    strategy_returns = []
    diagnostics = []

    time_to_maturity = maturity_days / TRADING_DAYS_PER_YEAR

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
            underlying_period_return + premium_fraction - call_payoff_fraction
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
) -> OverlayBacktestResult:
    """
    Backtest a synthetic protective collar overlay.

    The strategy owns the underlying, buys an out-of-the-money put, and sells
    an out-of-the-money call at each rebalance date.
    """
    aligned = pd.concat({"price": prices, "return": returns}, axis=1).dropna()
    vol = estimate_annualized_volatility(aligned["return"], window=volatility_window)

    rebalance_points = _rebalance_points(aligned.index, maturity_days)

    strategy_returns = []
    diagnostics = []

    time_to_maturity = maturity_days / TRADING_DAYS_PER_YEAR

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
                "underlying_period_return": underlying_period_return,
                "collar_period_return": collar_period_return,
            }
        )

    returns_df = pd.DataFrame(strategy_returns).set_index("date")
    diagnostics_df = pd.DataFrame(diagnostics)

    return OverlayBacktestResult(returns=returns_df, diagnostics=diagnostics_df)


def build_overlay_return_table(
    prices: pd.Series,
    returns: pd.Series,
    maturity_days: int = 21,
) -> pd.DataFrame:
    """
    Build a comparison table with passive, covered call, and collar returns.

    Returns are evaluated on the same rebalance dates to make comparison fair.
    """
    covered_call = covered_call_overlay_returns(
        prices=prices,
        returns=returns,
        maturity_days=maturity_days,
    )

    collar = collar_overlay_returns(
        prices=prices,
        returns=returns,
        maturity_days=maturity_days,
    )

    rebalance_index = covered_call.returns.index.intersection(collar.returns.index)

    passive_period_returns = (
        prices.loc[rebalance_index].pct_change().rename("passive_brazil_equity")
    )

    overlay_table = pd.concat(
        [
            passive_period_returns,
            covered_call.returns.loc[rebalance_index, "covered_call"],
            collar.returns.loc[rebalance_index, "collar"],
        ],
        axis=1,
    ).dropna()

    return overlay_table
"""Trade and exposure statistics, and cost attribution.

Everything here is derived strictly from `result.equity_curve` and `result.trades`,
so it is survivorship/leakage-safe by construction. The functions are pure: they
read attributes but never mutate the result, its series, or its trades.

Position/exposure and round-trip P&L are reconstructed from the trade list against
the equity curve index (no hidden state, no future data).
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from backtester.core import BacktestResult

_TRIP_EPS = 1e-12


def _is_datetime_index(equity: pd.Series) -> bool:
    return isinstance(equity.index, pd.DatetimeIndex)


def _bar_position(ts: object, equity: pd.Series) -> int:
    """Integer bar index of the last equity timestamp <= `ts`."""
    if not _is_datetime_index(equity):
        return 0
    return int((equity.index <= ts).sum()) - 1


def _net_position_per_bar(trades: list, equity: pd.Series) -> list[float]:
    """Net signed position at each equity bar, reconstructed solely from trades."""
    if not trades:
        return [0.0] * len(equity)
    ordered = sorted(trades, key=lambda t: t.ts)
    positions: list[float] = []
    net = 0.0
    idx = 0
    n = len(ordered)
    for t in equity.index:
        while idx < n and ordered[idx].ts <= t:
            net += ordered[idx].qty
            idx += 1
        positions.append(net)
    return positions


def _round_trips(trades: list, equity: pd.Series) -> list[tuple[float, float]]:
    """Reconstruct FIFO round-trips per symbol -> list of (realized_pnl, hold_bars)."""
    if not trades:
        return []
    ordered = sorted(trades, key=lambda t: t.ts)
    lots = defaultdict(deque)
    trips: list[tuple[float, float]] = []
    for t in ordered:
        qty = t.qty
        price = t.fill_price
        cost = t.commission + t.slippage
        entry_bar = _bar_position(t.ts, equity)
        if qty > 0:
            lots[t.symbol].append([qty, price, cost, entry_bar])
            continue
        remaining = -qty
        exit_qty = -qty if qty != 0 else 1.0
        while remaining > _TRIP_EPS and lots[t.symbol]:
            lot = lots[t.symbol][0]
            lot_qty, lot_price, lot_cost, lot_bar = lot
            matched = min(lot_qty, remaining)
            exit_cost = cost * (matched / exit_qty)
            entry_cost = lot_cost * (matched / lot_qty)
            pnl = (price - lot_price) * matched - exit_cost - entry_cost
            hold = float(entry_bar - lot_bar)
            trips.append((pnl, hold))
            lot[0] -= matched
            remaining -= matched
            if lot[0] <= _TRIP_EPS:
                lots[t.symbol].popleft()
    return trips


def trade_stats(result: "BacktestResult") -> dict:
    """Turnover, occupancy/exposure, win_rate, and avg_hold_bars for a result."""
    equity = result.equity_curve
    trades = result.trades
    n = len(equity)

    total_notional = sum(abs(t.qty * t.fill_price) for t in trades)
    mean_equity = float(equity.mean()) if n > 0 else 0.0
    turnover = total_notional / mean_equity if mean_equity > 0 else 0.0

    positions = _net_position_per_bar(trades, equity)
    occupancy = (sum(1 for p in positions if p != 0) / n) if n > 0 else 0.0

    trips = _round_trips(trades, equity)
    if trips:
        wins = sum(1 for pnl, _ in trips if pnl > 0)
        win_rate = wins / len(trips)
        avg_hold_bars = sum(h for _, h in trips) / len(trips)
    else:
        win_rate = 0.0
        avg_hold_bars = 0.0

    return {
        "turnover": turnover,
        "occupancy": occupancy,
        "win_rate": win_rate,
        "avg_hold_bars": avg_hold_bars,
    }


def cost_attribution(result: "BacktestResult") -> dict:
    """Commission/slippage totals and net return as fractions of mean equity.

    net_return = gross_return - (commission_fraction + slippage_fraction), all
    expressed as fractions so they are comparable to the other metrics.
    """
    trades = result.trades
    equity = result.equity_curve

    total_commission = sum(t.commission for t in trades)
    total_slippage = sum(t.slippage for t in trades)
    mean_equity = float(equity.mean()) if len(equity) > 0 else 0.0

    if len(equity) >= 2 and float(equity.iloc[0]) != 0:
        gross_return = float(equity.iloc[-1]) / float(equity.iloc[0]) - 1.0
    else:
        gross_return = 0.0

    if mean_equity > 0:
        commission_fraction = total_commission / mean_equity
        slippage_fraction = total_slippage / mean_equity
    else:
        commission_fraction = 0.0
        slippage_fraction = 0.0

    attributed_cost = commission_fraction + slippage_fraction
    net_return = gross_return - attributed_cost

    return {
        "total_commission": total_commission,
        "total_slippage": total_slippage,
        "gross_return": gross_return,
        "commission_fraction": commission_fraction,
        "slippage_fraction": slippage_fraction,
        "attributed_cost": attributed_cost,
        "net_return": net_return,
    }

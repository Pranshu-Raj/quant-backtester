"""Portfolio simulation state for the no-look-ahead engine.

``Portfolio`` owns all mutable simulation state (cash, positions, trade log)
and exposes a pure, input-immutable API. It holds no global state and never
mutates the ``Bar`` / ``Order`` objects passed into it — every recorded
``Trade`` is a freshly constructed frozen dataclass.

``equity_at`` values open positions at the most recent price seen for each
symbol, so a multi-symbol run stays point-in-time: when a bar for symbol S
arrives, only S's price advances; other positions keep their last known close.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from backtester.core import Bar, PortfolioState, Trade

# Below this absolute quantity a position is considered flat and is dropped.
_FLAT_EPSILON = 1e-12


class Portfolio:
    """Stateful but self-contained portfolio bookkeeping.

    Construction validates ``starting_cash``; all subsequent mutation happens
    exclusively through :meth:`apply` and the internally-owned price cache.
    """

    def __init__(self, starting_cash: float) -> None:
        if starting_cash <= 0:
            raise ValueError(f"starting_cash must be > 0, got {starting_cash!r}")
        self._cash: float = float(starting_cash)
        self._positions: Dict[str, float] = {}
        self._last_price: Dict[str, float] = {}
        self._trades: List[Trade] = []

    @property
    def cash(self) -> float:
        """Uninvested cash."""
        return self._cash

    @property
    def positions(self) -> Dict[str, float]:
        """A defensive copy of the current position book."""
        return dict(self._positions)

    @property
    def trades(self) -> List[Trade]:
        """A defensive copy of the executed-trade log."""
        return list(self._trades)

    def apply(
        self,
        bar: Bar,
        qty: float,
        fill_price: float,
        cost: Tuple[float, float],
    ) -> Trade:
        """Execute a fill and record it.

        ``cost`` is the ``(commission, slippage)`` pair returned by a cost
        model. ``qty`` is signed: positive buys, negative sells/shorts.
        Returns the freshly minted :class:`~backtester.core.Trade`.
        """
        commission, slippage = cost
        self._last_price[bar.symbol] = bar.close

        self._cash -= qty * fill_price + commission + slippage

        new_qty = self._positions.get(bar.symbol, 0.0) + qty
        if abs(new_qty) < _FLAT_EPSILON:
            self._positions.pop(bar.symbol, None)
            self._last_price.pop(bar.symbol, None)
        else:
            self._positions[bar.symbol] = new_qty

        trade = Trade(
            ts=bar.ts,
            symbol=bar.symbol,
            qty=qty,
            fill_price=fill_price,
            commission=commission,
            slippage=slippage,
        )
        self._trades.append(trade)
        return trade

    def equity_at(self, bar: Bar) -> float:
        """Mark-to-market equity using the latest known price per symbol.

        Updating the price cache here is portfolio-owned state, not input
        mutation; it keeps multi-symbol valuation point-in-time.
        """
        self._last_price[bar.symbol] = bar.close
        holdings = 0.0
        for symbol, qty in self._positions.items():
            price = self._last_price.get(symbol)
            if price is None:
                continue
            holdings += qty * price
        return self._cash + holdings

    def snapshot(self, bar: Bar) -> PortfolioState:
        """Build an immutable :class:`~backtester.core.PortfolioState` at ``bar``."""
        return PortfolioState(
            cash=self._cash,
            positions=dict(self._positions),
            equity=self.equity_at(bar),
        )

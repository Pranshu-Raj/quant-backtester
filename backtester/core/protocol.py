"""Public protocols/interface contracts.

These are the seams a user or adapter implements. The strategy protocol is the
*only* surface a user writes; the data-loader protocol is the seam the data
layer implements so the engine never depends on a concrete vendor (Principle 4).
"""

from __future__ import annotations

from typing import Iterator, Protocol

from .context import BarContext
from .models import Bar, Order, Universe


class StrategyProtocol(Protocol):
    """A trading strategy receives one bar at a time and returns orders.

    Implementations must not read data beyond the current bar — the
    ``BarContext`` offers no forward-access method, and any attempt raises
    ``LookAheadError`` and aborts the run.
    """

    def on_bar(self, ctx: BarContext) -> list[Order]:
        """Called by the engine for each bar in timestamp order."""
        ...


class PITDataLoaderProtocol(Protocol):
    """Point-in-time data source: yields strictly ascending bars for a universe."""

    def iter_bars(self, universe: Universe) -> Iterator[Bar]:
        """Yield ``Bar`` objects in strictly ascending ``ts`` order."""
        ...

"""``PITDataLoader`` — enforcement point #1 of the no-look-ahead guarantee.

The engine walks bars in timestamp order and only ever shows a strategy
state up to the current bar. That contract is meaningless if the bars
themselves arrive out of order, so this loader is the backstop: it
sorts incoming bars and refuses to yield any sequence that would let a
later timestamp appear before an earlier one.

Guarantee
--------
``iter_bars`` yields bars ordered by ``ts`` (ties broken by ``symbol`` so
the order is deterministic). Within a single symbol timestamps are
*strictly* ascending — a duplicate timestamp for one symbol is
ambiguous and cannot be made point-in-time, so it raises
:class:`PITDataError`.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Optional, Protocol

from backtester.core import Bar, Universe
from backtester.data.adapters import AdjustmentPolicy


class PITDataError(ValueError):
    """Raised when point-in-time ordering cannot be guaranteed."""


class DataAdapter(Protocol):
    """Object that can load raw bars for a universe."""

    def load(self, universe: Universe) -> list[Bar]:
        """Return bars for ``universe`` (filtering is the adapter's job)."""
        ...


class PITDataLoader:
    """Loads point-in-time bars and yields them in strictly ascending time.

    Parameters
    ----------
    adapter:
        Supplies raw bars for a given universe.
    adjustment:
        Optional :class:`~backtester.data.adapters.AdjustmentPolicy`
        applied to the loaded bars before ordering (adjustment at load time
        only — the engine never adjusts).
    """

    def __init__(
        self,
        adapter: DataAdapter,
        adjustment: Optional[AdjustmentPolicy] = None,
    ) -> None:
        self._adapter = adapter
        self._adjustment = adjustment

    def iter_bars(self, universe: Universe) -> Iterator[Bar]:
        """Yield bars in strictly ascending ``ts`` order.

        Sorts the adapter output by ``(ts, symbol)`` so the stream is
        globally non-decreasing in time and deterministic across symbols.
        Raises :class:`PITDataError` if any single symbol still has a
        duplicate/non-ascending timestamp after sorting.
        """
        bars = self._adapter.load(universe)
        if self._adjustment is not None:
            bars = self._adjustment.apply(bars)

        bars = sorted(bars, key=lambda b: (b.ts, b.symbol))
        self._enforce_ascending(bars)

        for bar in bars:
            yield bar

    @staticmethod
    def _enforce_ascending(bars: list[Bar]) -> None:
        """Raise if any symbol repeats or goes backward in time."""
        if not bars:
            return
        last_ts: Optional[datetime] = None
        last_symbol: Optional[str] = None
        for bar in bars:
            if last_symbol == bar.symbol and last_ts is not None and bar.ts <= last_ts:
                raise PITDataError(
                    f"non-ascending timestamps for symbol {bar.symbol!r}: "
                    f"{last_ts} followed by {bar.ts}; cannot guarantee no-look-ahead"
                )
            last_ts = bar.ts
            last_symbol = bar.symbol

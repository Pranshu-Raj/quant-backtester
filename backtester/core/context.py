"""Per-bar context handed to strategies, plus the no-look-ahead window wrapper.

``IndicatorWindow`` is the structural enforcement of Principle 1: a strategy may
only index ``series[0..t]``. Any attempt to read beyond ``t`` (including a
forward index ``t+1``) raises ``LookAheadError`` and aborts the run.

``BarContext`` deliberately exposes NO method to fetch future bars — the only
window it offers is the current one plus the portfolio snapshot at time ``t``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import Bar, LookAheadError


class IndicatorWindow:
    """A read-only view over a per-symbol indicator prefix ``series[0..t]``.

    Invariant: ``len(series) == t + 1``. The window refuses any index that
    would look ahead of the current bar.
    """

    def __init__(self, series: List[float], t: int) -> None:
        if len(series) != t + 1:
            raise ValueError(
                f"IndicatorWindow requires len(series) == t+1; got len(series)={len(series)}, t={t}"
            )
        self.series: List[float] = list(series)
        self.t: int = t

    def __getitem__(self, i: int) -> float:
        """Return ``series[i]``.

        Negative indices are resolved relative to the end of the prefix
        (``-1`` is the current bar ``t``). Any resolved index ``> t`` or out of
        range raises ``LookAheadError``.
        """
        if i < 0:
            idx = len(self.series) + i
        else:
            idx = i
        if idx < 0 or idx > self.t or idx >= len(self.series):
            raise LookAheadError(f"IndicatorWindow index {i} at t={self.t} would look ahead")
        return self.series[idx]

    def current(self) -> float:
        """The indicator value at the current bar ``t``."""
        return self.series[self.t]


@dataclass(frozen=True)
class PortfolioState:
    """Immutable snapshot of portfolio state at time ``t``."""

    cash: float
    positions: Dict[str, float]
    equity: float


@dataclass
class BarContext:
    """The only surface a strategy receives each bar.

    Constructed by the engine for bar ``t``. It carries the current ``Bar``,
    the precomputed indicator windows (each capped at ``t``), and the portfolio
    snapshot at ``t``. There is intentionally no method to reach bars ``> t``.
    """

    bar: Bar
    indicators: Dict[str, IndicatorWindow]
    portfolio: PortfolioState

    def indicator(self, name: str) -> IndicatorWindow:
        """Return the indicator window for ``name`` (capped at the current bar)."""
        return self.indicators[name]

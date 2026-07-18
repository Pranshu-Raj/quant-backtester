"""Immutable core data contracts for the backtesting platform.

These types are the shared vocabulary every other module depends on. They are
deliberately free of I/O, network, and mutable global state so that a run stays
pure and reproducible (ARCHITECTURE.md — Principle 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import List

from pydantic import BaseModel, field_validator, model_validator


class LookAheadError(Exception):
    """Raised when a strategy attempts to read data beyond the current bar.

    This is the hard-abort enforcement of the no-look-ahead guarantee
    (ARCHITECTURE.md — Principle 1). The engine treats it as fatal: the run is
    rejected, never warned.
    """


@dataclass(frozen=True)
class Bar:
    """A single OHLCV bar for one symbol.

    ``ts`` must be timezone-aware UTC. ``__post_init__`` normalizes any
    tz-aware value to UTC and rejects naive timestamps so downstream code can
    rely on a consistent, comparable timeline.

    ``split_ratio`` / ``dividend`` are optional corporate-action hints carried
    by the data layer's adjustment policy (default ``None``, ignored by the
    engine). They are part of the contract because the data adapter populates
    them on load.
    """

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    split_ratio: float | None = None
    dividend: float | None = None

    def __post_init__(self) -> None:
        ts = self.ts
        if ts.tzinfo is None:
            raise ValueError("Bar.ts must be timezone-aware (UTC)")
        if ts.utcoffset() != timezone.utc.utcoffset(None):
            object.__setattr__(self, "ts", ts.astimezone(timezone.utc))


@dataclass(frozen=True)
class Trade:
    """A single executed fill. ``qty`` is signed (negative = sell/short)."""

    ts: datetime
    symbol: str
    qty: float
    fill_price: float
    commission: float
    slippage: float


@dataclass(frozen=True)
class Order:
    """An instruction emitted by a strategy for the next fill opportunity.

    ``price=None`` means a market order; ``kind`` selects the fill semantics.
    ``qty`` is signed.
    """

    symbol: str
    qty: float
    price: float | None = None
    kind: str = "market"


class Universe(BaseModel):
    """The "what we test" definition: a symbol set plus an inclusive range.

    Symbols are normalized to upper-cased, stripped, de-duplicated tokens with
    at least one non-empty entry. ``start`` must strictly precede ``end``.
    """

    symbols: List[str]
    start: date
    end: date

    @field_validator("symbols", mode="after")
    @classmethod
    def _normalize_symbols(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        for raw in value:
            token = raw.strip().upper()
            if token and token not in cleaned:
                cleaned.append(token)
        if not cleaned:
            raise ValueError("Universe.symbols must contain at least one non-empty symbol")
        return cleaned

    @model_validator(mode="after")
    def _check_range(self) -> "Universe":
        if self.start >= self.end:
            raise ValueError("Universe requires start < end")
        return self

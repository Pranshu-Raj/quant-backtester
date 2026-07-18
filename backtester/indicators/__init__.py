"""Vectorized, pure, windowed indicators and signal primitives.

Public API:
  technical: sma, ema, rsi, macd, bollinger, rolling_vol, cross
  signals:   threshold, rank, make_signal
  precompute: precompute (single indicator-computation entry point for the engine)
"""

from __future__ import annotations

from .precompute import precompute
from .signals import make_signal, rank, threshold
from .technical import bollinger, cross, ema, macd, rolling_vol, rsi, sma

__all__ = [
    "sma",
    "ema",
    "rsi",
    "macd",
    "bollinger",
    "rolling_vol",
    "cross",
    "threshold",
    "rank",
    "make_signal",
    "precompute",
]

"""Backtester engine — the simulation core and no-look-ahead enforcement point.

Public surface:
    run        — execute a point-in-time backtest (``engine.run``)
    Portfolio  — self-contained cash/position bookkeeping
    FillModel  — resolves signal -> fill execution price
"""

from __future__ import annotations

from .engine import run
from .fill import FillModel
from .portfolio import Portfolio

__all__ = ["run", "Portfolio", "FillModel"]

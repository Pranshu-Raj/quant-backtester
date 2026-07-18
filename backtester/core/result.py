"""Backtest result contract.

``BacktestResult`` is the immutable artifact produced by the engine. It always
carries an ``AuditReport`` (Principle 5 — a result without an audit is
incomplete) plus the determinism manifest (``config_hash``, ``data_hash``,
``engine_version``) required to reproduce a run byte-for-byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from .models import Trade

if TYPE_CHECKING:
    # Avoid a runtime import cycle: backtester.audit imports BacktestResult from
    # this package under TYPE_CHECKING too. At runtime the field is just a string
    # annotation, so no cycle is formed.
    from backtester.audit import AuditReport

# Bump on any change that affects run output (fills, costs, hashing). Part of the
# determinism manifest that must match for two runs to be comparable.
ENGINE_VERSION = "0.1.0"


@dataclass(frozen=True)
class BacktestResult:
    """Immutable outcome of a backtest run."""

    equity_curve: pd.Series
    trades: list[Trade]
    config_hash: str
    data_hash: str
    engine_version: str
    audit: "AuditReport"

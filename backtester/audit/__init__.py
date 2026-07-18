"""Mandatory overfitting/trust audit for the backtester platform.

Public exports:
    - AuditReport: immutable audit result (deflated_sharpe, pbo, verdict, notes)
    - audit: run the mandatory audit on a backtest result
"""

from __future__ import annotations

from .audit import audit
from .report import AuditReport

__all__ = ["AuditReport", "audit"]

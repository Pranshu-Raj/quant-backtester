"""Tearsheet analytics for the no-look-ahead backtester.

All metrics are computed only from the returned equity curve and trades, so they
are survivorship- and leakage-safe by construction (per backtester-architecture.md,
PRINCIPLE 5 / analytics §3.6). Every function is pure: it never mutates its inputs.
"""

from backtester.analytics.metrics import cagr, calmar, max_drawdown, sharpe, sortino
from backtester.analytics.stats import cost_attribution, trade_stats
from backtester.analytics.tearsheet import print_tearsheet, tearsheet

__all__ = [
    "cagr",
    "sharpe",
    "sortino",
    "calmar",
    "max_drawdown",
    "trade_stats",
    "cost_attribution",
    "tearsheet",
    "print_tearsheet",
]

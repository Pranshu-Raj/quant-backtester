"""Tearsheet assembly and a concise, user-facing text report."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backtester.analytics.metrics import cagr, calmar, max_drawdown, sharpe, sortino
from backtester.analytics.stats import cost_attribution, trade_stats

if TYPE_CHECKING:
    from backtester.core import BacktestResult


def tearsheet(result: "BacktestResult") -> dict:
    """Combine metrics + trade stats + cost attribution into one structured dict."""
    stats = trade_stats(result)
    ca = cost_attribution(result)
    return {
        "cagr": cagr(result.equity_curve),
        "sharpe": sharpe(result.equity_curve),
        "sortino": sortino(result.equity_curve),
        "calmar": calmar(result.equity_curve),
        "max_drawdown": max_drawdown(result.equity_curve),
        "turnover": stats["turnover"],
        "occupancy": stats["occupancy"],
        "win_rate": stats["win_rate"],
        "avg_hold": stats["avg_hold_bars"],
        "cost_attribution": ca,
        "n_trades": len(result.trades),
    }


def print_tearsheet(result: "BacktestResult") -> str:
    """Return a concise, human-readable tearsheet string (for CLI/stdout)."""
    t = tearsheet(result)
    ca = t["cost_attribution"]
    lines = [
        "Tearsheet",
        "--------",
        f"CAGR           : {t['cagr']:.4f}",
        f"Sharpe         : {t['sharpe']:.4f}",
        f"Sortino        : {t['sortino']:.4f}",
        f"Calmar         : {t['calmar']:.4f}",
        f"Max Drawdown   : {t['max_drawdown']:.4f}",
        f"Turnover       : {t['turnover']:.4f}",
        f"Occupancy      : {t['occupancy']:.4f}",
        f"Win Rate       : {t['win_rate']:.4f}",
        f"Avg Hold (bars): {t['avg_hold']:.4f}",
        f"Trades         : {t['n_trades']}",
        "Costs",
        f"  Commission   : {ca['total_commission']:.4f}",
        f"  Slippage     : {ca['total_slippage']:.4f}",
        f"  Net Return   : {ca['net_return']:.4f}",
        "",
        "Audit (mandatory overfitting check)",
        "-----------------------------------",
        f"  Verdict            : {result.audit.verdict}",
        f"  Deflated Sharpe    : {result.audit.deflated_sharpe:.4f}",
        f"  PBO                : {result.audit.pbo:.4f}",
        f"  Notes              : {result.audit.notes}",
    ]
    return "\n".join(lines)

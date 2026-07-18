"""Tearsheet assembly and a concise, user-facing text report."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backtester.analytics.metrics import cagr, calmar, max_drawdown, sharpe, sortino
from backtester.analytics.stats import cost_attribution, trade_stats

if TYPE_CHECKING:
    from backtester.core import BacktestResult
    from backtester.forward import ForwardResult


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


def _fmt_date(index: object) -> str:
    ts = index[0]  # Timestamp-like
    return str(ts.date())


def print_forward(result: "ForwardResult") -> str:
    """Return a human-readable in-sample vs out-of-sample gap report."""
    is_r = result.in_sample
    oos_r = result.out_of_sample
    g = result.gap

    def row(label: str, is_v: float, oos_v: float) -> str:
        gap_v = oos_v - is_v
        return f"{label:<16}: {is_v:>12.4f}   {oos_v:>14.4f}   {gap_v:>10.4f}"

    lines = [
        "Forward Validation",
        "-----------------",
        f"Split date      : {result.split_date}",
        f"In-sample       : {_fmt_date(is_r.equity_curve.index)} .. "
        f"{_fmt_date(is_r.equity_curve.index[-1:])}  ({len(is_r.equity_curve)} bars)",
        f"Out-of-sample   : {_fmt_date(oos_r.equity_curve.index)} .. "
        f"{_fmt_date(oos_r.equity_curve.index[-1:])}  ({len(oos_r.equity_curve)} bars)",
        "",
        f"{'':<16}  {'In-sample':>12}   {'Out-of-sample':>14}   {'Gap':>10}",
        row("CAGR", g.in_sample_cagr, g.out_of_sample_cagr),
        row("Sharpe", g.in_sample_sharpe, g.out_of_sample_sharpe),
        row("Sortino", g.in_sample_sortino, g.out_of_sample_sortino),
        row("Max Drawdown", g.in_sample_max_drawdown, g.out_of_sample_max_drawdown),
        row("Deflated Sharpe", g.in_sample_deflated_sharpe, g.out_of_sample_deflated_sharpe),
        "",
        f"Forward verdict  : {g.verdict}",
        f"Notes            : {g.notes}",
    ]
    return "\n".join(lines)

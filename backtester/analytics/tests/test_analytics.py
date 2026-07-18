"""Self-contained tests for backtester.analytics.

The equity curve and trades are built synthetically from ``backtester.core``'s
``Trade`` / ``BacktestResult`` types. A minimal local fallback is used only if
the core package is unavailable, keeping the suite runnable as the platform is
scaffolded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

try:  # Prefer the real contracts once backtester.core is built.
    from backtester.core import BacktestResult, Trade
except ImportError:  # pragma: no cover - scaffolding fallback
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Trade:
        ts: object
        symbol: str
        qty: float
        fill_price: float
        commission: float = 0.0
        slippage: float = 0.0

    @dataclass
    class BacktestResult:
        equity_curve: object
        trades: list
        config_hash: str = ""
        data_hash: str = ""
        engine_version: str = "0.1.0"
        audit: object = None


from backtester.analytics import (
    cagr,
    calmar,
    cost_attribution,
    max_drawdown,
    print_tearsheet,
    sharpe,
    sortino,
    tearsheet,
    trade_stats,
)


def _dt(value: str) -> pd.Timestamp:
    return pd.Timestamp(value)


def _make_result(equity: pd.Series, trades: list) -> BacktestResult:
    from backtester.audit.report import AuditReport

    return BacktestResult(
        equity_curve=equity,
        trades=trades,
        config_hash="test",
        data_hash="test",
        engine_version="0.1.0",
        audit=AuditReport(
            deflated_sharpe=0.5, pbo=0.0, verdict="warn", notes="test audit"
        ),
    )


# --- metrics: cagr ---------------------------------------------------------


def test_cagr_doubling_over_one_year():
    start = _dt("2020-01-01")
    end = start + pd.Timedelta(days=365.25)  # exactly one calendar year
    eq = pd.Series([100.0, 200.0], index=[start, end])
    assert cagr(eq) == pytest.approx(1.0, rel=1e-12)


def test_cagr_rangeindex_fallback():
    # 253 points => 252 intervals => one "year" at the 252 default.
    eq = pd.Series(np.linspace(100.0, 200.0, 253))
    assert cagr(eq) == pytest.approx(1.0, rel=1e-9)


# --- metrics: max_drawdown -------------------------------------------------


def test_max_drawdown_known_dip():
    eq = pd.Series(
        [100.0, 110.0, 99.0, 121.0],
        index=pd.date_range("2020-01-31", periods=4, freq="ME"),
    )
    assert max_drawdown(eq) == pytest.approx(-0.10, rel=1e-12)


# --- metrics: sharpe / sortino / calmar -----------------------------------


def test_sharpe_sortino_first_principles():
    eq = pd.Series(
        [100.0, 110.0, 99.0, 121.0],
        index=pd.date_range("2020-01-31", periods=4, freq="ME"),
    )
    periods = 12
    rets = eq.pct_change().dropna()

    ref_sharpe = rets.mean() / rets.std(ddof=1) * np.sqrt(periods)
    downside = np.sqrt(np.mean(np.minimum(rets, 0.0) ** 2))
    ref_sortino = rets.mean() / downside * np.sqrt(periods)

    assert sharpe(eq, periods=periods) == pytest.approx(ref_sharpe, rel=1e-9)
    assert sortino(eq, periods=periods) == pytest.approx(ref_sortino, rel=1e-9)


def test_calmar_equals_cagr_over_abs_mdd():
    eq = pd.Series(
        [100.0, 110.0, 99.0, 121.0],
        index=pd.date_range("2020-01-31", periods=4, freq="ME"),
    )
    expected = cagr(eq) / abs(max_drawdown(eq))
    assert calmar(eq) == pytest.approx(expected, rel=1e-12)


# --- purity: inputs are never mutated -------------------------------------


def test_metrics_do_not_mutate_input():
    eq = pd.Series(
        [100.0, 110.0, 99.0, 121.0],
        index=pd.date_range("2020-01-31", periods=4, freq="ME"),
    )
    original = eq.copy()
    cagr(eq)
    sharpe(eq)
    sortino(eq)
    calmar(eq)
    max_drawdown(eq)
    pd.testing.assert_series_equal(eq, original)


# --- trade_stats -----------------------------------------------------------


def test_trade_stats_hand_calc():
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    equity = pd.Series([10000.0] * 10, index=idx)
    trades = [
        Trade(
            ts=_dt("2020-01-01"),
            symbol="A",
            qty=10,
            fill_price=100.0,
            commission=0.0,
            slippage=0.0,
        ),
        Trade(
            ts=_dt("2020-01-04"),
            symbol="A",
            qty=-10,
            fill_price=110.0,
            commission=0.0,
            slippage=0.0,
        ),
    ]
    result = _make_result(equity, trades)
    stats = trade_stats(result)

    # Single winning round-trip.
    assert stats["win_rate"] == pytest.approx(1.0)
    # Entry at bar 0, exit at bar 3 => 3 bars held.
    assert stats["avg_hold_bars"] == pytest.approx(3.0)
    # Net position is non-zero for bars 0,1,2 of 10 => 0.3.
    assert stats["occupancy"] == pytest.approx(0.3)
    # Turnover = (10*100 + 10*110) / mean(equity) = 2100 / 10000.
    assert stats["turnover"] == pytest.approx(0.21)


def test_trade_stats_empty():
    eq = pd.Series([100.0, 100.0], index=pd.date_range("2020-01-01", periods=2))
    result = _make_result(eq, [])
    stats = trade_stats(result)
    assert stats["win_rate"] == 0.0
    assert stats["avg_hold_bars"] == 0.0
    assert stats["occupancy"] == 0.0


# --- cost_attribution ------------------------------------------------------


def test_cost_attribution_net_equals_gross_minus_cost():
    idx = pd.date_range("2020-01-01", periods=2, freq="D")
    equity = pd.Series([100.0, 200.0], index=idx)
    trades = [
        Trade(
            ts=_dt("2020-01-01"),
            symbol="A",
            qty=1,
            fill_price=100.0,
            commission=1.0,
            slippage=2.0,
        ),
        Trade(
            ts=_dt("2020-01-02"),
            symbol="A",
            qty=-1,
            fill_price=200.0,
            commission=1.0,
            slippage=2.0,
        ),
    ]
    result = _make_result(equity, trades)
    ca = cost_attribution(result)

    assert ca["total_commission"] == pytest.approx(2.0)
    assert ca["total_slippage"] == pytest.approx(4.0)
    assert ca["gross_return"] == pytest.approx(1.0)
    # net = gross - (commission_fraction + slippage_fraction)
    expected_net = ca["gross_return"] - ca["commission_fraction"] - ca["slippage_fraction"]
    assert ca["net_return"] == pytest.approx(expected_net, rel=1e-12)
    # explicit: 1.0 - (2 + 4) / 150 = 1.0 - 0.04 = 0.96
    assert ca["net_return"] == pytest.approx(0.96, rel=1e-12)


# --- tearsheet -------------------------------------------------------------


def test_tearsheet_keys_and_report():
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    equity = pd.Series([10000.0] * 10, index=idx)
    trades = [
        Trade(
            ts=_dt("2020-01-01"),
            symbol="A",
            qty=10,
            fill_price=100.0,
            commission=0.0,
            slippage=0.0,
        ),
        Trade(
            ts=_dt("2020-01-04"),
            symbol="A",
            qty=-10,
            fill_price=110.0,
            commission=0.0,
            slippage=0.0,
        ),
    ]
    result = _make_result(equity, trades)

    t = tearsheet(result)
    expected_keys = [
        "cagr",
        "sharpe",
        "sortino",
        "calmar",
        "max_drawdown",
        "turnover",
        "occupancy",
        "win_rate",
        "avg_hold",
        "cost_attribution",
        "n_trades",
    ]
    for key in expected_keys:
        assert key in t
    assert t["n_trades"] == 2
    assert isinstance(t["cost_attribution"], dict)
    assert set(t["cost_attribution"]) >= {
        "total_commission",
        "total_slippage",
        "net_return",
    }

    report = print_tearsheet(result)
    assert isinstance(report, str)
    assert "Tearsheet" in report

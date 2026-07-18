"""Real integration tests for the backtester engine.

These exercise the engine against the *real* sibling modules (core, data,
indicators, costs, audit) — no mocks of the no-look-ahead machinery.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd
import pytest

from backtester.core import (
    BacktestResult,
    Bar,
    Config,
    LookAheadError,
    Order,
    Trade,
    Universe,
)
from backtester.data import CSVLocalAdapter, PITDataLoader
from backtester.engine import FillModel, Portfolio, run

_SYMBOL = "AAA"


def _bar(ts: datetime, close: float, symbol: str = _SYMBOL) -> Bar:
    return Bar(
        ts=ts,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000.0,
        symbol=symbol,
    )


def _make_csv(tmp_path: Path, n_bars: int = 30) -> Path:
    """Write a tiny single-symbol CSV with a gently rising close."""
    path = tmp_path / "prices.csv"
    lines = ["date,symbol,open,high,low,close,volume"]
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(n_bars):
        ts = base + pd.Timedelta(days=i)
        price = 100.0 + float(i)
        date_str = ts.date().isoformat()
        lines.append(
            f"{date_str},{_SYMBOL},{price},{price},{price},{price},1000"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _make_loader(tmp_path: Path, n_bars: int = 30) -> PITDataLoader:
    path = _make_csv(tmp_path, n_bars)
    return PITDataLoader(CSVLocalAdapter(path))


def _make_config(n_bars: int = 30) -> Config:
    start = date(2024, 1, 1)
    end = date(2024, 1, 1) + pd.Timedelta(days=n_bars - 1).to_pytimedelta()
    return Config(
        universe=Universe(symbols=[_SYMBOL], start=start, end=end),
        data_path="dummy.csv",
        starting_cash=100_000.0,
        fill_model="next_close",
        fill_lag=1,
        cost_model="flat_per_trade",
        cost_params={"commission": 1.0},
        trials=1,
    )


class _BuyOnFirstBar:
    """Trivial strategy: buy a fixed quantity on the very first bar only."""

    def __init__(self, qty: float = 10.0) -> None:
        self._qty = qty
        self._done = False

    def on_bar(self, ctx) -> List[Order]:  # noqa: ANN001 - ctx is BarContext
        if self._done:
            return []
        self._done = True
        return [Order(symbol=_SYMBOL, qty=self._qty)]


class _LeakyStrategy:
    """Strategy that peeks one bar into the future -> must raise LookAheadError."""

    def on_bar(self, ctx) -> List[Order]:
        window = ctx.indicators["sma_50"]
        # Reading window.t + 1 is exactly one step past the current bar.
        _ = window[window.t + 1]
        return []


class _BuyEveryBar:
    """Emits a market buy on every bar. The last bar's order cannot fill
    inside the window, so it is forced down the end-of-data fallback path —
    exactly the case the equity/trades desync bug lived in."""

    def __init__(self, qty: float = 5.0) -> None:
        self._qty = qty

    def on_bar(self, ctx) -> List[Order]:  # noqa: ANN001 - ctx is BarContext
        return [Order(symbol=_SYMBOL, qty=self._qty)]


# --- Portfolio math ---------------------------------------------------------


def test_portfolio_apply_buy_math() -> None:
    portfolio = Portfolio(starting_cash=1000.0)
    bar = _bar(datetime(2024, 1, 1, tzinfo=timezone.utc), close=50.0)

    trade = portfolio.apply(bar, qty=10.0, fill_price=50.0, cost=(1.0, 0.0))

    assert portfolio.cash == pytest.approx(499.0)  # 1000 - (10*50 + 1)
    assert portfolio.positions == {"AAA": 10.0}
    assert isinstance(trade, Trade)
    assert trade.qty == 10.0
    assert trade.commission == 1.0
    assert trade.slippage == 0.0
    # Equity marks the 10 shares at the valuation bar's close (50).
    assert portfolio.equity_at(bar) == pytest.approx(999.0)


def test_portfolio_apply_sell_math() -> None:
    portfolio = Portfolio(starting_cash=1000.0)
    buy = _bar(datetime(2024, 1, 1, tzinfo=timezone.utc), close=50.0)
    sell = _bar(datetime(2024, 1, 2, tzinfo=timezone.utc), close=60.0)

    portfolio.apply(buy, qty=10.0, fill_price=50.0, cost=(1.0, 0.0))
    portfolio.apply(sell, qty=-4.0, fill_price=60.0, cost=(0.5, 0.0))

    # cash: 499 (after buy) - (-4*60 + 0.5) = 499 + 239.5 = 738.5
    assert portfolio.cash == pytest.approx(738.5)
    assert portfolio.positions == {"AAA": 6.0}
    # equity: 738.5 + 6*60 = 1098.5
    assert portfolio.equity_at(sell) == pytest.approx(1098.5)


def test_portfolio_rejects_non_positive_cash() -> None:
    with pytest.raises(ValueError):
        Portfolio(starting_cash=0.0)


# --- FillModel --------------------------------------------------------------


def test_fill_model_next_close_returns_next_bar_close() -> None:
    fm = FillModel(mode="next_close", lag=1)
    current = _bar(datetime(2024, 1, 1, tzinfo=timezone.utc), close=10.0)
    nxt = _bar(datetime(2024, 1, 2, tzinfo=timezone.utc), close=11.0)
    assert fm.price(current, nxt) == pytest.approx(11.0)


def test_fill_model_falls_back_at_data_end() -> None:
    fm = FillModel(mode="next_close", lag=1)
    current = _bar(datetime(2024, 1, 1, tzinfo=timezone.utc), close=10.0)
    assert fm.price(current, None) == pytest.approx(10.0)


def test_fill_model_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        FillModel(mode="twap")


# --- No-look-ahead enforcement ---------------------------------------------


def test_look_ahead_access_raises(tmp_path: Path) -> None:
    config = _make_config()
    loader = _make_loader(tmp_path)

    with pytest.raises(LookAheadError):
        run(config, loader, _LeakyStrategy())


# --- End-to-end run ---------------------------------------------------------


def test_run_returns_result_with_equity_and_audit(tmp_path: Path) -> None:
    config = _make_config()
    loader = _make_loader(tmp_path)

    result = run(config, loader, _BuyOnFirstBar(qty=10.0))

    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) == 30
    assert len(result.trades) == 1
    executed = result.trades[0]
    assert isinstance(executed, Trade)
    assert executed.qty == 10.0
    assert executed.symbol == _SYMBOL
    assert result.audit is not None
    assert result.audit.verdict in ("pass", "warn")
    assert isinstance(result.config_hash, str) and result.config_hash
    assert isinstance(result.data_hash, str) and result.data_hash
    assert result.engine_version


def test_run_equity_curve_is_indexed_by_ts(tmp_path: Path) -> None:
    config = _make_config()
    loader = _make_loader(tmp_path)

    result = run(config, loader, _BuyOnFirstBar())

    assert result.equity_curve.index.name == "ts"
    assert isinstance(result.equity_curve.index, pd.DatetimeIndex)


def test_run_end_of_data_fill_reflected_in_equity(tmp_path: Path) -> None:
    config = _make_config(n_bars=10)
    loader = _make_loader(tmp_path, n_bars=10)

    result = run(config, loader, _BuyEveryBar(qty=5.0))

    # One order per bar -> the final one lands in the end-of-data fallback.
    assert len(result.trades) == 10

    # Reconstruct final equity from the trade log and compare to the curve's
    # last point. The end-of-data fix makes these agree; without it the curve
    # tail ignored the boundary fills and the two would diverge.
    cash = config.starting_cash
    position = 0.0
    for t in result.trades:
        cash -= t.qty * t.fill_price + t.commission + t.slippage
        position += t.qty
    last_close = result.trades[-1].fill_price  # single symbol: mark == last fill
    assert cash + position * last_close == pytest.approx(result.equity_curve.iloc[-1])

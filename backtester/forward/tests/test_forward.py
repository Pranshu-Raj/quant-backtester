"""Forward-validation tests: split correctness, gap reporting, fresh-instance, guards."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backtester.cli import _resolve_bundled
from backtester.core import Config, LookAheadError, Universe
from backtester.data import AdjustmentPolicy, CSVLocalAdapter, PITDataLoader
from backtester.examples.sma_crossover import SMACrossover
from backtester.forward import ForwardResult, run_forward, split_universe

_DATA_PATH = _resolve_bundled("data/prices.csv")


def _loader() -> PITDataLoader:
    adapter = CSVLocalAdapter(path=_DATA_PATH)
    return PITDataLoader(adapter=adapter, adjustment=AdjustmentPolicy(mode="back"))


def _config(trials: int = 1) -> Config:
    return Config(
        universe=Universe(symbols=["AAA"], start=date(2023, 1, 2), end=date(2024, 12, 31)),
        starting_cash=100_000.0,
        fill_model="next_close",
        fill_lag=1,
        cost_model="flat_per_trade",
        cost_params={"commission": 1.0},
        data_path=str(_DATA_PATH),
        adjustment="back",
        seed=42,
        audit=True,
        trials=trials,
    )


def test_run_forward_reports_gap() -> None:
    res = run_forward(_config(), _loader(), lambda: SMACrossover(), split=0.6)
    assert isinstance(res, ForwardResult)
    assert res.gap.verdict in ("robust", "degraded", "failed")
    assert isinstance(res.gap.in_sample_sharpe, float)
    assert isinstance(res.gap.out_of_sample_sharpe, float)
    # In-sample ends strictly before out-of-sample begins.
    assert res.in_sample.equity_curve.index[-1] < res.out_of_sample.equity_curve.index[0]


def test_split_has_no_overlap() -> None:
    u = Universe(symbols=["AAA"], start=date(2023, 1, 2), end=date(2024, 12, 31))
    loader = _loader()
    is_u, oos_u, split_date = split_universe(loader, u, 0.6)
    assert is_u.end == split_date
    assert oos_u.start == split_date + timedelta(days=1)

    is_max = max(b.ts for b in loader.iter_bars(is_u))
    oos_min = min(b.ts for b in loader.iter_bars(oos_u))
    assert is_max < oos_min


def test_fresh_strategy_per_leg() -> None:
    calls: list[int] = []

    def factory():
        calls.append(1)
        return SMACrossover()

    run_forward(_config(), _loader(), factory, split=0.6)
    assert len(calls) == 2


def test_invalid_split_raises() -> None:
    u = Universe(symbols=["AAA"], start=date(2023, 1, 2), end=date(2024, 12, 31))
    loader = _loader()
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            split_universe(loader, u, bad)


def test_short_range_raises() -> None:
    # Valid universe, but the data window is too short to split (< 4 bars).
    u = Universe(symbols=["AAA"], start=date(2023, 1, 2), end=date(2023, 1, 4))
    loader = _loader()
    with pytest.raises(ValueError):
        split_universe(loader, u, 0.6)


def test_forward_leaky_aborts() -> None:
    from backtester.examples.leaky import strategy as leaky

    with pytest.raises(LookAheadError):
        run_forward(_config(), _loader(), lambda: type(leaky)(), split=0.6)

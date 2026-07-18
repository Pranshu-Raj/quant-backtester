"""Self-contained tests for the point-in-time data layer.

All fixtures are built in ``tmp_path``; no network, no external files.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from backtester.core import Bar, Universe
from backtester.data import (
    AdjustmentPolicy,
    CSVLocalAdapter,
    PITDataLoader,
)
from backtester.data.loader import PITDataError
from backtester.data.universe import date_range

CSV_HEADER = "date,symbol,open,high,low,close,volume"


def _write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text(CSV_HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def _shuffled_csv() -> list[str]:
    """Six bars (2 symbols x 3 dates) in intentionally wrong order."""
    return [
        "2023-01-03,BBB,10,11,9,10,100",
        "2023-01-01,AAA,20,21,19,20,200",
        "2023-01-03,AAA,20,22,19,21,210",
        "2023-01-01,BBB,10,11,9,10,100",
        "2023-01-02,BBB,10,12,9,11,120",
        "2023-01-02,AAA,20,21,18,20,205",
    ]


def _two_day_universe() -> Universe:
    return Universe(symbols=["AAA", "BBB"], start="2023-01-01", end="2023-01-03")


def test_csv_adapter_loads_two_symbols_with_correct_dtypes(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path / "prices.csv", _shuffled_csv())

    bars = CSVLocalAdapter(path=csv_path).load(_two_day_universe())

    assert len(bars) == 6
    assert {b.symbol for b in bars} == {"AAA", "BBB"}
    for bar in bars:
        # numeric OHLCV are real floats, not numpy/pandas scalars leaking through
        assert isinstance(bar.open, float)
        assert isinstance(bar.high, float)
        assert isinstance(bar.low, float)
        assert isinstance(bar.close, float)
        assert isinstance(bar.volume, float)
        # timestamps are tz-aware UTC
        assert bar.ts.tzinfo is not None
        assert bar.ts.utcoffset() == timedelta(0)
        assert bar.ts.hour == 0 and bar.ts.minute == 0  # date-only -> midnight


def test_csv_adapter_filters_by_symbol_and_date_range(tmp_path: Path) -> None:
    rows = [
        "2022-12-31,AAA,1,1,1,1,1",    # out of date range
        "2023-01-01,CCC,1,1,1,1,1",    # out of universe symbols
        "2023-01-01,AAA,20,21,19,20,200",
        "2023-01-02,AAA,20,21,18,20,205",
        "2023-01-03,AAA,20,22,19,21,210",
    ]
    csv_path = _write_csv(tmp_path / "prices.csv", rows)

    bars = CSVLocalAdapter(path=csv_path).load(_two_day_universe())

    # only the in-range AAA rows survive (BBB absent from this fixture)
    assert [b.ts.date().isoformat() for b in bars] == [
        "2023-01-01",
        "2023-01-02",
        "2023-01-03",
    ]
    assert all(b.symbol == "AAA" for b in bars)


def test_iter_bars_yields_ascending_ts_even_when_shuffled(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path / "prices.csv", _shuffled_csv())
    loader = PITDataLoader(
        adapter=CSVLocalAdapter(path=csv_path),
        adjustment=AdjustmentPolicy(mode="back"),
    )

    bars = list(loader.iter_bars(_two_day_universe()))

    assert len(bars) == 6
    # globally non-decreasing in time (ties across symbols are allowed)
    timestamps = [b.ts for b in bars]
    assert timestamps == sorted(timestamps)
    # within each symbol, time is strictly ascending
    for symbol in {"AAA", "BBB"}:
        sym_ts = [b.ts for b in bars if b.symbol == symbol]
        assert sym_ts == sorted(sym_ts)
        assert all(sym_ts[i] < sym_ts[i + 1] for i in range(len(sym_ts) - 1))


def test_iter_bars_rejects_duplicate_timestamps(tmp_path: Path) -> None:
    # AAA appears twice on 2023-01-02 -> ambiguous, not point-in-time
    rows = [
        "2023-01-01,AAA,20,21,19,20,200",
        "2023-01-02,AAA,20,21,18,20,205",
        "2023-01-02,AAA,21,22,20,21,207",
    ]
    csv_path = _write_csv(tmp_path / "prices.csv", rows)
    loader = PITDataLoader(adapter=CSVLocalAdapter(path=csv_path))

    with pytest.raises(PITDataError):
        list(loader.iter_bars(Universe(symbols=["AAA"], start="2023-01-01", end="2023-01-03")))


def _split_fixture() -> list[Bar]:
    """One symbol, a 2:1 split on the middle bar."""
    return [
        Bar(
            ts=datetime(2023, 1, 1, tzinfo=timezone.utc),
            open=102, high=103, low=99, close=100, volume=1, symbol="X", split_ratio=1,
        ),
        Bar(
            ts=datetime(2023, 1, 2, tzinfo=timezone.utc),
            open=51, high=52, low=49, close=50, volume=1, symbol="X", split_ratio=2,
        ),
        Bar(
            ts=datetime(2023, 1, 3, tzinfo=timezone.utc),
            open=53, high=54, low=50, close=52, volume=1, symbol="X", split_ratio=1,
        ),
    ]


def test_adjustment_back_leaves_last_bar_unchanged_and_scales_earlier() -> None:
    policy = AdjustmentPolicy(mode="back")
    adjusted = policy.apply(_split_fixture())

    # cumulative factors R = [1, 2, 2]; anchor = R_last = 2
    assert adjusted[2].close == pytest.approx(52.0)   # last bar unchanged
    assert adjusted[0].close == pytest.approx(50.0)   # pre-split scaled down by 2
    assert adjusted[1].close == pytest.approx(50.0)
    # OHLC scaled by the same per-bar factor (high of bar0: 103 -> 51.5)
    assert adjusted[0].open == pytest.approx(51.0)
    assert adjusted[0].high == pytest.approx(51.5)
    assert adjusted[0].low == pytest.approx(49.5)


def test_adjustment_forward_anchors_first_bar() -> None:
    policy = AdjustmentPolicy(mode="forward")
    adjusted = policy.apply(_split_fixture())

    # anchor = R_first = 1
    assert adjusted[0].close == pytest.approx(100.0)  # first bar unchanged
    assert adjusted[2].close == pytest.approx(104.0)  # later scaled up by 2


def test_adjustment_is_pure_does_not_mutate_input() -> None:
    bars = _split_fixture()
    before = [(b.open, b.close) for b in bars]
    AdjustmentPolicy(mode="back").apply(bars)
    after = [(b.open, b.close) for b in bars]
    assert before == after  # input untouched


def test_adjustment_no_op_without_columns() -> None:
    bars = [
        Bar(
            ts=datetime(2023, 1, 1, tzinfo=timezone.utc),
            open=10, high=11, low=9, close=10, volume=1, symbol="Z",
        ),
        Bar(
            ts=datetime(2023, 1, 2, tzinfo=timezone.utc),
            open=12, high=13, low=11, close=12, volume=1, symbol="Z",
        ),
    ]
    adjusted = AdjustmentPolicy(mode="back").apply(bars)
    assert adjusted == bars  # factor defaults to 1.0 -> identical values


def test_date_range_helper_returns_tuple_of_dates() -> None:
    uni = Universe(symbols=["AAA"], start="2023-01-01", end="2023-12-31")
    start, end = date_range(uni)
    assert isinstance(start, date)
    assert isinstance(end, date)
    assert (start, end) == (date(2023, 1, 1), date(2023, 12, 31))

"""Self-contained contract tests for ``backtester.core``.

These tests import only from the public ``backtester.core`` surface (no sibling
module imports) and verify the invariants every other module relies on:

* ``Config`` validation rejects bad inputs (incl. a disabled audit).
* ``Universe`` rejects inverted ranges and normalizes symbols to uppercase.
* ``IndicatorWindow`` enforces no-look-ahead (forward index aborts; ``-1`` is current).
* ``config_hash`` is deterministic for equal configs and differs otherwise.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from backtester.core import (
    Bar,
    Config,
    IndicatorWindow,
    LookAheadError,
    Universe,
    config_hash,
)


def _valid_universe() -> Universe:
    return Universe(symbols=["aapl"], start=date(2020, 1, 1), end=date(2021, 1, 1))


# --- Config validation -------------------------------------------------------


def test_config_rejects_negative_cash() -> None:
    with pytest.raises(ValidationError):
        Config(universe=_valid_universe(), data_path="dummy.csv", starting_cash=-1.0)


def test_config_rejects_audit_disabled() -> None:
    with pytest.raises(ValidationError, match="audit cannot be disabled"):
        Config(universe=_valid_universe(), data_path="dummy.csv", audit=False)


def test_config_rejects_zero_fill_lag() -> None:
    with pytest.raises(ValidationError):
        Config(universe=_valid_universe(), data_path="dummy.csv", fill_lag=0)


def test_config_defaults_are_valid() -> None:
    cfg = Config(universe=_valid_universe(), data_path="dummy.csv")
    assert cfg.starting_cash == 100_000.0
    assert cfg.fill_lag == 1
    assert cfg.audit is True


# --- Universe validation -----------------------------------------------------


def test_universe_rejects_start_after_end() -> None:
    with pytest.raises(ValidationError):
        Universe(symbols=["AAPL"], start=date(2021, 1, 1), end=date(2020, 1, 1))


def test_universe_normalizes_symbols_uppercase() -> None:
    uni = Universe(symbols=["aapl", " msft "], start=date(2020, 1, 1), end=date(2021, 1, 1))
    assert uni.symbols == ["AAPL", "MSFT"]


def test_universe_rejects_empty_symbols() -> None:
    with pytest.raises(ValidationError):
        Universe(symbols=["  ", ""], start=date(2020, 1, 1), end=date(2021, 1, 1))


# --- IndicatorWindow no-look-ahead -------------------------------------------


def test_indicator_window_forward_index_raises() -> None:
    series = [1.0, 2.0, 3.0]
    t = 2  # len(series) == t + 1
    window = IndicatorWindow(series, t)
    with pytest.raises(LookAheadError):
        _ = window[t + 1]


def test_indicator_window_negative_one_is_current() -> None:
    series = [1.0, 2.0, 3.0]
    t = 2
    window = IndicatorWindow(series, t)
    assert window[-1] == series[t] == 3.0
    assert window.current() == 3.0
    assert window[-2] == 2.0


def test_indicator_window_valid_range_accessible() -> None:
    series = [10.0, 20.0, 30.0]
    window = IndicatorWindow(series, t=2)
    assert window[0] == 10.0
    assert window[2] == 30.0


# --- config_hash determinism -------------------------------------------------


def test_config_hash_stable_for_equal_configs() -> None:
    cfg_a = Config(universe=_valid_universe(), data_path="dummy.csv", starting_cash=50_000.0)
    cfg_b = Config(universe=_valid_universe(), data_path="dummy.csv", starting_cash=50_000.0)
    assert config_hash(cfg_a) == config_hash(cfg_b)


def test_config_hash_differs_for_different_configs() -> None:
    cfg_a = Config(universe=_valid_universe(), data_path="dummy.csv", starting_cash=50_000.0)
    cfg_b = Config(universe=_valid_universe(), data_path="dummy.csv", starting_cash=60_000.0)
    assert config_hash(cfg_a) != config_hash(cfg_b)


# --- Bar tz-awareness ---------------------------------------------------------


def test_bar_requires_tz_aware_ts() -> None:
    with pytest.raises(ValueError):
        Bar(
            ts=datetime(2020, 1, 1, 12, 0),
            open=1.0,
            high=2.0,
            low=0.5,
            close=1.5,
            volume=100.0,
            symbol="AAPL",
        )

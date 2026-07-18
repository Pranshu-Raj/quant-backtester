"""Self-contained tests for the indicators module using synthetic series."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtester.indicators import (
    bollinger,
    cross,
    ema,
    macd,
    make_signal,
    precompute,
    rank,
    rolling_vol,
    rsi,
    sma,
    threshold,
)


def _fixture_prices() -> pd.Series:
    """Deterministic 40-point price path (trend + wobble)."""
    rng = np.random.default_rng(20240717)
    steps = rng.normal(0, 1.0, size=40).cumsum()
    prices = 100.0 + 2.0 * steps + np.linspace(0, 5, 40)
    return pd.Series(prices, dtype="float64")


def test_sma_matches_hand_rolled_rolling_mean() -> None:
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    expected = s.rolling(3).mean()
    pd.testing.assert_series_equal(sma(s, 3), expected)


def test_ema_is_causal_and_same_length() -> None:
    s = _fixture_prices()
    out = ema(s, 12)
    assert len(out) == len(s)
    # First value equals the input's first value (Wilder seeding, no future use).
    assert out.iloc[0] == pytest.approx(s.iloc[0])


def _reference_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Independent textbook Wilder RSI implemented as an explicit loop."""
    p = list(prices.to_numpy())
    n = len(p)
    out = [float("nan")] * n
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        d = p[i] - p[i - 1]
        gains[i] = d if d > 0 else 0.0
        losses[i] = -d if d < 0 else 0.0

    avg_gain = avg_loss = 0.0
    for i in range(period, n):
        if i == period:
            avg_gain = sum(gains[1 : period + 1]) / period
            avg_loss = sum(losses[1 : period + 1]) / period
        else:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0.0:
            out[i] = 100.0
        elif avg_gain == 0.0:
            out[i] = 0.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return pd.Series(out, index=prices.index, dtype="float64")


def test_rsi_matches_reference_formula() -> None:
    s = _fixture_prices()
    actual = rsi(s, 14)
    expected = _reference_rsi(s, 14)
    actual_vals = actual.to_numpy()
    expected_vals = expected.to_numpy()
    mask = ~np.isnan(expected_vals)
    assert np.allclose(actual_vals[mask], expected_vals[mask], atol=1e-6)


def test_rsi_prefix_is_nan() -> None:
    s = pd.Series(np.arange(1, 30, dtype="float64"))
    out = rsi(s, 14)
    # First `period` values must be NaN (no look-ahead into the window).
    assert out.iloc[:14].isna().all()


def test_rsi_known_answers_for_monotonic_series() -> None:
    # Closed-form expected values, no reference implementation needed:
    # pure uptrend -> 100 (no losses); pure downtrend -> 0 (no gains);
    # flat -> NaN (no movement either way).
    up = pd.Series(np.linspace(100.0, 200.0, 30))
    down = pd.Series(np.linspace(200.0, 100.0, 30))
    flat = pd.Series(np.full(30, 100.0))

    assert rsi(up, 14).iloc[-1] == pytest.approx(100.0)
    assert rsi(down, 14).iloc[-1] == pytest.approx(0.0)
    assert np.isnan(rsi(flat, 14).iloc[-1])


def test_cross_true_only_on_up_cross_bar() -> None:
    fast = pd.Series([1.0, 1.0, 3.0, 4.0, 5.0, 6.0])
    slow = pd.Series([2.0, 2.0, 2.0, 2.0, 2.0, 2.0])
    result = cross(fast, slow)
    assert result.sum() == 1
    assert bool(result.iloc[2]) is True
    assert bool(result.iloc[0]) is False  # first bar is never a cross


def test_cross_handles_nan_prefix_gracefully() -> None:
    fast = pd.Series([np.nan, np.nan, 1.0, 3.0])
    slow = pd.Series([2.0, 2.0, 2.0, 2.0])
    result = cross(fast, slow)
    assert result.dtype == bool
    assert bool(result.iloc[0]) is False
    assert bool(result.iloc[1]) is False
    assert bool(result.iloc[2]) is False
    assert bool(result.iloc[3]) is True  # 1 -> 3 crosses above 2


def test_bollinger_band_ordering_and_length() -> None:
    s = _fixture_prices()
    mid, upper, lower = bollinger(s, 20, 2.0)
    assert len(mid) == len(s) == len(upper) == len(lower)
    valid = mid.notna()
    assert (upper[valid] >= mid[valid]).all()
    assert (mid[valid] >= lower[valid]).all()


def test_macd_shapes_and_hist_relation() -> None:
    s = _fixture_prices()
    line, signal_line, hist = macd(s)
    assert len(line) == len(signal_line) == len(hist)
    pd.testing.assert_series_equal(hist, line - signal_line)


def test_rolling_vol_same_length_with_nan_prefix() -> None:
    s = _fixture_prices()
    out = rolling_vol(s, 20)
    assert len(out) == len(s)
    assert out.iloc[:20].isna().all()


def test_threshold_operators() -> None:
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    assert threshold(s, ">", 2.0).tolist() == [False, False, True, True]
    assert threshold(s, "<", 3.0).tolist() == [True, True, False, False]
    assert threshold(s, ">=", 3.0).tolist() == [False, False, True, True]
    assert threshold(s, "<=", 2.0).tolist() == [True, True, False, False]
    with pytest.raises(ValueError):
        threshold(s, "==", 2.0)


def test_rank_is_percentile() -> None:
    s = pd.Series([4.0, 1.0, 3.0, 2.0])
    r = rank(s, ascending=True)
    # 1 -> 0.25, 2 -> 0.5, 3 -> 0.75, 4 -> 1.0 (lowest gets smallest rank).
    assert r.round(6).tolist() == [1.0, 0.25, 0.75, 0.5]


def test_make_signal_is_aligned_and_conjunction() -> None:
    a = pd.Series([True, False, True, True], index=["w", "x", "y", "z"])
    b = pd.Series([True, True, False, True], index=["w", "x", "y", "z"])
    result = make_signal(a, b)
    assert result.tolist() == [True, False, False, True]
    assert list(result.index) == ["w", "x", "y", "z"]


def test_precompute_returns_keyed_dict_with_expected_names_and_length() -> None:
    close = np.arange(1, 101, dtype="float64")
    bars = {"AAA": pd.DataFrame({"close": close})}
    result = precompute(bars)

    assert set(result.keys()) == {"AAA"}
    expected_names = {
        "sma_20",
        "sma_50",
        "sma_200",
        "ema_12",
        "ema_26",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_hist",
        "bb_mid",
        "bb_upper",
        "bb_lower",
        "vol_20",
    }
    assert expected_names.issubset(set(result["AAA"].keys()))

    for name, series in result["AAA"].items():
        assert len(series) == len(close)
        assert isinstance(series, pd.Series)

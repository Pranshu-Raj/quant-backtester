"""Vectorized, pure technical indicators.

Every function takes a :class:`pandas.Series` (float) and returns a *same-length*
:class:`pandas.Series`. Indicators are windowed by construction: a value at index
``t`` depends only on values at ``[0..t]`` (no future reads, no look-ahead). The
engine is responsible for slicing the prefix ``[0..t]`` per bar; these functions
never peek forward.

All functions are pure: inputs are never mutated, and no global/network state is
touched. Dependencies are limited to pandas and numpy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average over a trailing ``window``.

    Returns a same-length series; the first ``window - 1`` values are ``NaN``.
    """
    return pd.Series(series, dtype="float64").rolling(window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average with the given ``span`` (alpha = 2 / (span + 1)).

    Uses Wilder-style recursive smoothing (``adjust=False``) so it is strictly
    causal. Returns a same-length series.
    """
    return pd.Series(series, dtype="float64").ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index.

    The average gain/loss is smoothed recursively (Wilder's method), seeded with
    the simple mean of the first ``period`` deltas. Returns a same-length series;
    the first ``period`` values are ``NaN``. Flat prices (no movement) yield
    ``NaN``; a lossless run yields ``100``.
    """
    s = pd.Series(series, dtype="float64")
    n = len(s)
    out = pd.Series(np.nan, index=s.index, dtype="float64")
    if n <= period:
        return out

    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    # Wilder's smoothing is the ewm recurrence (adjust=False) with an SMA seed at
    # position ``period``. The seed-corrected closed form below is exact and fully
    # vectorized: y[t] = ewm[t] + (seed - ewm[seed]) * (1 - alpha) ** (t - seed).
    alpha = 1.0 / period
    ewm_gain = gain.ewm(alpha=alpha, adjust=False).mean().to_numpy()
    ewm_loss = loss.ewm(alpha=alpha, adjust=False).mean().to_numpy()

    seed_pos = period  # gain valid from position 1; mean of positions 1..period.
    seed_gain = float(gain.iloc[1 : seed_pos + 1].mean())
    seed_loss = float(loss.iloc[1 : seed_pos + 1].mean())

    positions = np.arange(n) - seed_pos
    valid = positions >= 0
    corr_gain = np.where(
        valid, (seed_gain - ewm_gain[seed_pos]) * ((1.0 - alpha) ** positions), np.nan
    )
    corr_loss = np.where(
        valid, (seed_loss - ewm_loss[seed_pos]) * ((1.0 - alpha) ** positions), np.nan
    )
    avg_gain = np.where(valid, ewm_gain + corr_gain, np.nan)
    avg_loss = np.where(valid, ewm_loss + corr_loss, np.nan)

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi_vals = 100.0 - 100.0 / (1.0 + rs)
    rsi_vals = np.where(avg_loss == 0.0, 100.0, rsi_vals)
    rsi_vals = np.where((avg_gain == 0.0) & (avg_loss == 0.0), np.nan, rsi_vals)
    rsi_vals = np.where(~valid, np.nan, rsi_vals)

    out = pd.Series(rsi_vals, index=s.index, dtype="float64")
    return out


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Moving Average Convergence Divergence.

    Returns ``(macd_line, signal_line, histogram)``, all same-length series.
    ``macd_line = ema(fast) - ema(slow)``; ``signal_line`` is the EMA of the line;
    ``histogram = macd_line - signal_line``.
    """
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(
    series: pd.Series,
    window: int = 20,
    k: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands.

    Returns ``(mid, upper, lower)`` where ``mid`` is the SMA, and the bands sit
    ``k`` population-standard-deviations away. All same-length series.
    """
    mid = sma(series, window)
    std = pd.Series(series, dtype="float64").rolling(window).std(ddof=0)
    upper = mid + k * std
    lower = mid - k * std
    return mid, upper, lower


def rolling_vol(series: pd.Series, window: int) -> pd.Series:
    """Trailing rolling volatility (std-dev of simple returns) over ``window``.

    Returns a same-length series; the first ``window`` values are ``NaN``.
    """
    returns = pd.Series(series, dtype="float64").pct_change()
    return returns.rolling(window).std(ddof=0)


def cross(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """Boolean series True only on the bar where ``fast`` crosses *above* ``slow``.

    A cross occurs at ``t`` iff ``fast[t] > slow[t]`` and ``fast[t-1] <= slow[t-1]``.
    NaN values are treated as "not above" (so the prefix returns ``False``), and the
    first bar is never flagged (there is no previous bar to cross from).
    """
    f = pd.Series(fast, dtype="float64")
    s = pd.Series(slow, dtype="float64")
    above = f > s
    prev_above = above.shift(1)
    # `.eq(False)` (not unary `~`) keeps proper boolean negation in pandas 3.0+.
    prev_not_above = prev_above.fillna(False).eq(False)
    crossed = above & prev_not_above
    crossed = crossed.fillna(False)
    if len(crossed):
        crossed.iloc[0] = False
    return crossed.astype(bool)

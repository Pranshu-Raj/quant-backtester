"""Core tearsheet metrics.

Functions operate on a single `pd.Series` equity curve indexed by date. They are
pure (no mutation of the input) and survivorship/leakage-safe because they only
ever observe the curve and its own index — never any external or future data.

Conventions:
- CAGR is the geometric annualized growth rate derived from the elapsed span of a
  `DatetimeIndex` (so "equity doubling over 1 year" => CAGR 1.0 exactly). With a
  non-datetime index it falls back to `(n_points - 1) / periods_per_year` years.
- Sharpe / Sortino / Calmar annualize by `periods` (default 252, i.e. daily).
- `max_drawdown` returns a non-positive number (e.g. -0.2 for a 20% drop).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _as_returns(equity: pd.Series) -> pd.Series:
    """Periodic simple returns. Pure: returns a new series, never mutates input."""
    if len(equity) < 2:
        return pd.Series(dtype=float)
    return equity.pct_change().dropna()


def _periods_per_year(equity: pd.Series) -> float:
    """Infer periods per year from a DatetimeIndex; default 252 for daily/unknown."""
    index = equity.index
    if isinstance(index, pd.DatetimeIndex) and len(index) > 1:
        deltas = index[1:] - index[:-1]
        median_days = float(deltas.median().total_seconds()) / 86_400.0
        if median_days <= 0:
            return 252.0
        if median_days <= 4.0:  # ~daily (or finer)
            return 252.0
        return 365.25 / median_days
    return 252.0


def _elapsed_years(equity: pd.Series, periods_per_year: float) -> float:
    """Years spanned by the curve: calendar span for DatetimeIndex, else bar count."""
    index = equity.index
    if isinstance(index, pd.DatetimeIndex) and len(index) > 1:
        span_days = (index[-1] - index[0]).total_seconds() / 86_400.0
        if span_days > 0:
            return span_days / 365.25
    if len(equity) > 1:
        return (len(equity) - 1) / periods_per_year
    return 1.0


def cagr(equity: pd.Series) -> float:
    """Annualized growth rate. Doubling over one year => 1.0."""
    if len(equity) < 2:
        return 0.0
    start = float(equity.iloc[0])
    end = float(equity.iloc[-1])
    if start <= 0:
        raise ValueError("equity curve must be strictly positive for CAGR")
    years = _elapsed_years(equity, _periods_per_year(equity))
    if years <= 0:
        return 0.0
    return (end / start) ** (1.0 / years) - 1.0


def sharpe(equity: pd.Series, risk_free: float = 0.0, periods: int = 252) -> float:
    """Annualized Sharpe ratio of periodic returns (sample std, ddof=1)."""
    returns = _as_returns(equity)
    if len(returns) == 0:
        return 0.0
    mean = float(returns.mean())
    std = float(returns.std(ddof=1))
    if std == 0.0:
        return 0.0
    excess = mean - risk_free / periods
    return excess / std * np.sqrt(periods)


def sortino(equity: pd.Series, risk_free: float = 0.0, periods: int = 252) -> float:
    """Annualized Sortino ratio using downside deviation (over all periods)."""
    returns = _as_returns(equity)
    if len(returns) == 0:
        return 0.0
    mean = float(returns.mean())
    downside = np.minimum(returns - risk_free / periods, 0.0)
    downside_dev = float(np.sqrt(np.mean(downside**2)))
    if downside_dev == 0.0:
        return 0.0
    excess = mean - risk_free / periods
    return excess / downside_dev * np.sqrt(periods)


def max_drawdown(equity: pd.Series) -> float:
    """Largest peak-to-trough decline as a non-positive fraction (e.g. -0.2)."""
    if len(equity) == 0:
        return 0.0
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return float(drawdown.min())


def calmar(equity: pd.Series, periods: int = 252) -> float:
    """CAGR divided by |max drawdown|."""
    mdd = max_drawdown(equity)
    if mdd == 0.0:
        return 0.0
    return cagr(equity) / abs(mdd)

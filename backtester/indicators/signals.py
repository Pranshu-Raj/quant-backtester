"""Signal primitives built on top of the vectorized indicators.

These are pure, windowed helpers that turn numeric series into boolean (or ranked)
signals evaluated at bar ``t`` using only data up to ``t``. No global/network state
is touched and inputs are never mutated.
"""

from __future__ import annotations

import operator
from typing import Callable

import pandas as pd

_COMPARATORS: dict[str, Callable[[pd.Series, float], pd.Series]] = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}


def threshold(series: pd.Series, op: str, value: float) -> pd.Series:
    """Boolean series where ``series <op> value`` holds.

    ``op`` must be one of ``">"``, ``"<"``, ``">="``, ``"<="``. Comparisons with
    ``NaN`` yield ``False``.
    """
    if op not in _COMPARATORS:
        raise ValueError(f"Unsupported op {op!r}; expected one of {sorted(_COMPARATORS)}")
    s = pd.Series(series, dtype="float64")
    return _COMPARATORS[op](s, value).fillna(False).astype(bool)


def rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    """Percentile rank of each value in ``[0, 1]``.

    Ties share the average rank. ``ascending=True`` means larger values get a higher
    rank. Returns a same-length series.
    """
    s = pd.Series(series, dtype="float64")
    return s.rank(pct=True, ascending=ascending)


def make_signal(*conditions: pd.Series) -> pd.Series:
    """Logical AND of the given boolean series, aligned by the first series' index.

    Every condition is cast to bool, aligned to the first condition's index, and
    missing labels are treated as ``False``. Requires at least one condition.
    """
    if not conditions:
        raise ValueError("make_signal requires at least one boolean condition")

    base = conditions[0].astype(bool)
    index = base.index
    result = base.reindex(index).fillna(False)
    for cond in conditions[1:]:
        other = cond.astype(bool).reindex(index).fillna(False)
        result = result & other
    return result.astype(bool)

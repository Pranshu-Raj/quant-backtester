"""Self-contained tests for the mandatory overfitting audit.

These tests pass equity curves straight to ``audit`` — no fake result object
needed (``audit`` reads only the curve).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtester.audit import AuditReport, audit


def _good_curve() -> pd.Series:
    """Steady upward equity with mild noise -> high Sharpe."""
    rng = np.random.default_rng(42)
    returns = 0.01 + rng.normal(0.0, 0.002, size=200)
    equity = 1000.0 * np.cumprod(1.0 + returns)
    return pd.Series(equity)


def _flat_curve() -> pd.Series:
    """Constant equity -> no genuine Sharpe."""
    return pd.Series(np.full(200, 1000.0))


def _negative_curve() -> pd.Series:
    """Downward equity -> negative Sharpe."""
    rng = np.random.default_rng(7)
    returns = -0.005 + rng.normal(0.0, 0.002, size=200)
    equity = 1000.0 * np.cumprod(1.0 + returns)
    return pd.Series(equity)


def test_audit_returns_audit_report() -> None:
    report = audit(_good_curve())
    assert isinstance(report, AuditReport)
    assert report.verdict in ("pass", "warn")


def test_deflated_sharpe_decreases_with_trials() -> None:
    result = _good_curve()
    previous: float | None = None
    for trials in (1, 5, 20, 100):
        deflated = audit(result, trials=trials).deflated_sharpe
        if previous is not None:
            assert deflated <= previous + 1e-9
        previous = deflated


def test_good_curve_passes() -> None:
    assert audit(_good_curve(), trials=1).verdict == "pass"


def test_flat_curve_warns() -> None:
    assert audit(_flat_curve(), trials=1).verdict == "warn"


def test_negative_curve_warns() -> None:
    assert audit(_negative_curve(), trials=1).verdict == "warn"


def test_trials_clamped_to_minimum() -> None:
    result = _good_curve()
    at_zero = audit(result, trials=0).deflated_sharpe
    at_one = audit(result, trials=1).deflated_sharpe
    assert at_zero == at_one


def test_pbo_zero_for_single_trial() -> None:
    # No configurations searched => no selection overfitting => PBO is 0.
    assert audit(_good_curve(), trials=1).pbo == 0.0


def test_pbo_monotonic_and_bounded_in_trials() -> None:
    result = _good_curve()
    previous: float | None = None
    for trials in (1, 2, 5, 20, 100):
        pbo = audit(result, trials=trials).pbo
        assert 0.0 <= pbo <= 1.0
        if previous is not None:
            assert pbo >= previous - 1e-9
        previous = pbo
    # With many trials searched the overfitting probability is strictly positive.
    assert audit(result, trials=100).pbo > 0.0

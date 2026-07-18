"""Mandatory overfitting/trust audit (Principle 5 of backtester-architecture.md).

`audit()` is invoked by the engine on EVERY result and MUST NOT be skippable.
It does not read any config flag to disable itself; the only way to skip it is
an explicit environment flag used solely for internal tests, which is out of
scope for this scaffold.

The scaffold computes a correct, documented Deflated Sharpe Ratio (DSR)
approximation. The full Baixa-Lopez / Bailey "Deflated Sharpe Ratio" paper
formula is driven by the number of trials, the variance of the Sharpe estimate,
and the expected maximum Sharpe over the trials. For the v0.1 scaffold we use a
defensible, monotonic approximation:

    deflated_sharpe = sharpe / sqrt(1 + log(max(trials, 1)))

Rationale: searching over more trials (more configurations / parameters) inflates
the *observed* Sharpe because the best of many noisy estimates is selected. The
deflator therefore grows with `trials`, so `deflated_sharpe` strictly decreases
as `trials` grows for any fixed strategy Sharpe. This captures the core
overfitting intuition required by FEATURES.md (DSR increases with fewer trials).
"""

from __future__ import annotations

import math

import pandas as pd

from backtester.analytics import sharpe

from .report import AuditReport

# Pass verdict when the deflated Sharpe is at least this value.
PASS_THRESHOLD = 1.0


def _pbo_of_trials(trials: int) -> float:
    """Backtest-overfitting probability proxy from configurations searched.

    With a single configuration there is no selection, so the probability the
    chosen strategy is overfit is 0. As more configurations are searched the
    chance the *selected* (best-looking) one is a false positive rises toward 1.
    This is a documented v0.5 scaffold; the empirical PBO (which needs the
    N-trial performance distribution) is a v1.0 item.
    """
    if trials <= 1:
        return 0.0
    return 1.0 - 1.0 / float(trials)


def audit(equity_curve: pd.Series, trials: int = 1) -> AuditReport:
    """Run the mandatory overfitting audit on a backtest result.

    Args:
        equity_curve: The strategy's equity curve as a ``pd.Series`` (the
            ``backtester.core.BacktestResult.equity_curve`` in production).
        trials: Number of trials / configurations searched. More trials inflate
            the observed Sharpe, so the deflated Sharpe shrinks as ``trials``
            grows. Clamped to be ``>= 1``.

    Returns:
        An ``AuditReport`` with the deflated Sharpe, a ``"pass"``/``"warn"``
        verdict, and an explanatory note. The verdict is ``"warn"`` when the
        deflated Sharpe is below ``PASS_THRESHOLD`` (1.0).

    Note:
        This function is intentionally not gated by any config flag. The engine
        must call it on every run (Principle 5).
    """
    trials = max(int(trials), 1)  # ensure trials >= 1

    pbo = _pbo_of_trials(trials)

    raw_sharpe = sharpe(equity_curve)

    # Deflated Sharpe Ratio (scaffold approximation):
    #   deflated_sharpe = sharpe / sqrt(1 + log(max(trials, 1)))
    # The deflator grows with trials, so deflated_sharpe is non-increasing in
    # trials for a fixed strategy Sharpe.
    deflator = math.sqrt(1.0 + math.log(trials))
    deflated_sharpe = raw_sharpe / deflator

    verdict = "pass" if deflated_sharpe >= PASS_THRESHOLD else "warn"
    notes = (
        f"Deflated Sharpe {deflated_sharpe:.3f} "
        f"(trials={trials}, threshold={PASS_THRESHOLD:.1f}); "
        f"{'acceptable' if verdict == 'pass' else 'below threshold'}"
    )

    return AuditReport(
        deflated_sharpe=float(deflated_sharpe),
        pbo=pbo,
        verdict=verdict,
        notes=notes,
    )

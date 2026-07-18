"""Audit report contract for the mandatory overfitting/trust audit.

See `backtester-architecture.md` Principle 5: every result ships with an
overfitting audit. A result without an `AuditReport` is incomplete. The audit
runs on every `BacktestResult` and cannot be disabled via config.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditReport:
    """Immutable result of the overfitting/trust audit.

    Attributes:
        deflated_sharpe: Sharpe ratio adjusted downward for the number of
            trials searched (Deflated Sharpe Ratio).
        pbo: Backtest-overfitting probability. v0.5 computes a real value;
            the scaffold defaults it to 0.0.
        verdict: ``"pass"`` or ``"warn"``. ``"warn"`` means the deflated Sharpe
            is below the acceptance threshold and the result may be overfit.
        notes: Human-readable explanation of the verdict.
    """

    deflated_sharpe: float
    pbo: float = 0.0
    verdict: str = "warn"
    notes: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in ("pass", "warn"):
            raise ValueError(
                f"verdict must be 'pass' or 'warn', got {self.verdict!r}"
            )

"""Validated run configuration (ARCHITECTURE.md — Principle 2, pure runs).

``Config`` is the pydantic schema that the CLI / API map 1:1 onto. The audit
flag is intentionally non-disablable: the overfitting audit is mandatory on
every result (Principle 5), so ``audit=False`` is rejected at validation time.
"""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, field_validator

from .models import Universe


class Config(BaseModel):
    """Fully-validated backtest configuration.

    Construction validates every invariant. Invalid values raise
    ``pydantic.ValidationError`` with field-level paths so callers can surface
    precisely what is wrong.
    """

    universe: Universe
    starting_cash: float = 100_000.0
    fill_model: str = "next_close"
    fill_lag: int = 1
    cost_model: str = "flat_per_trade"
    cost_params: Dict = {}
    seed: Optional[int] = None
    audit: bool = True
    trials: int = 1
    data_path: str
    adjustment: str = "back"

    @field_validator("starting_cash")
    @classmethod
    def _positive_cash(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("starting_cash must be > 0")
        return value

    @field_validator("fill_lag")
    @classmethod
    def _nonzero_lag(cls, value: int) -> int:
        if value < 1:
            raise ValueError("fill_lag must be >= 1")
        return value

    @field_validator("trials")
    @classmethod
    def _at_least_one_trial(cls, value: int) -> int:
        if value < 1:
            raise ValueError("trials must be >= 1")
        return value

    @field_validator("audit")
    @classmethod
    def _audit_mandatory(cls, value: bool) -> bool:
        if value is False:
            raise ValueError("audit cannot be disabled")
        return value

    @field_validator("adjustment")
    @classmethod
    def _valid_adjustment(cls, value: str) -> str:
        if value not in ("back", "forward", ""):
            raise ValueError("adjustment must be 'back', 'forward', or ''")
        return value

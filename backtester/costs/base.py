from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BaseCostModel(Protocol):
    """Pluggable cost-model contract (PRINCIPLE 4, backtester-architecture.md).

    Cost models are swappable implementations behind a stable interface. The
    engine calls :meth:`apply` once per fill and receives an
    ``(commission, slippage)`` pair. The core never imports a concrete cost
    model, so new models drop in with no engine edits.

    Implementations MUST stay pure (PRINCIPLE 2): ``apply`` must not mutate
    ``fill_price`` or ``qty`` and must be deterministic for fixed inputs.
    """

    def apply(self, fill_price: float, qty: float) -> tuple[float, float]:
        """Return ``(commission, slippage)`` for a single fill.

        Args:
            fill_price: Execution price of the fill (per share / unit).
            qty: Signed quantity of the fill. Cost depends on trade magnitude,
                not direction, so implementations should use ``abs(qty)``.

        Returns:
            A 2-tuple of non-negative floats ``(commission, slippage)``.
        """
        ...

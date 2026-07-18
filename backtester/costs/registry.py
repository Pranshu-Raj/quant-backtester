from __future__ import annotations

from typing import Any

from backtester.costs.base import BaseCostModel
from backtester.costs.models import FlatPerTrade, PctOfValue, VolumeSlippage

COST_MODELS: dict[str, type[BaseCostModel]] = {
    "flat_per_trade": FlatPerTrade,
    "pct_of_value": PctOfValue,
    "volume_slippage": VolumeSlippage,
}


def get_cost_model(name: str, params: dict[str, Any] | None = None) -> BaseCostModel:
    """Build a cost-model instance by registry name.

    Args:
        name: One of the keys in :data:`COST_MODELS`.
        params: Keyword arguments forwarded to the model constructor.

    Returns:
        An initialized :class:`BaseCostModel` instance.

    Raises:
        ValueError: If ``name`` is not a registered cost model.
    """
    model_cls = COST_MODELS.get(name)
    if model_cls is None:
        raise ValueError(
            f"Unknown cost model {name!r}. Available: {sorted(COST_MODELS)}"
        )
    return model_cls(**(params or {}))

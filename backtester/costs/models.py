from __future__ import annotations

from backtester.costs.base import BaseCostModel


class FlatPerTrade(BaseCostModel):
    """Flat commission charged per trade, with zero slippage (v0.1, SPRINTS S5).

    The simplest pluggable cost: ``apply`` returns ``(commission, 0.0)``
    regardless of fill price or size.
    """

    def __init__(self, commission: float = 1.0) -> None:
        if commission < 0:
            raise ValueError(f"commission must be >= 0, got {commission!r}")
        self.commission = commission

    def apply(self, fill_price: float, qty: float) -> tuple[float, float]:
        return (self.commission, 0.0)


class PctOfValue(BaseCostModel):
    """Commission as a percentage of trade notional value (v0.1->v0.5, FEATURES D).

    ``apply`` returns ``(abs(qty) * fill_price * rate, 0.0)`` — cost scales with
    trade size and price, with zero slippage.
    """

    def __init__(self, rate: float = 0.0005) -> None:
        if rate < 0:
            raise ValueError(f"rate must be >= 0, got {rate!r}")
        self.rate = rate

    def apply(self, fill_price: float, qty: float) -> tuple[float, float]:
        commission = abs(qty) * fill_price * self.rate
        return (commission, 0.0)


class VolumeSlippage(BaseCostModel):
    """Flat commission plus slippage proportional to trade notional value (FEATURES D).

    ``apply`` returns ``(commission, abs(qty) * fill_price * slippage_rate)``.
    """

    def __init__(
        self, commission: float = 1.0, slippage_rate: float = 0.0001
    ) -> None:
        if commission < 0:
            raise ValueError(f"commission must be >= 0, got {commission!r}")
        if slippage_rate < 0:
            raise ValueError(f"slippage_rate must be >= 0, got {slippage_rate!r}")
        self.commission = commission
        self.slippage_rate = slippage_rate

    def apply(self, fill_price: float, qty: float) -> tuple[float, float]:
        slippage = abs(qty) * fill_price * self.slippage_rate
        return (self.commission, slippage)

"""Reference strategy: SMA(50) / SMA(200) crossover.

Conforms to ``StrategyProtocol`` (implements ``on_bar(ctx) -> list[Order]``).
It only ever reads ``ctx.indicators`` (each capped at the current bar ``t``) and
``ctx.portfolio`` (state at ``t``), so it cannot look ahead. If a strategy
instead indexed ``ctx.indicators["sma_50"][t + 1]``, the ``IndicatorWindow``
would raise ``LookAheadError`` and abort the run — that is the guarantee.

Implementation note
-------------------
The engine fills orders with ``fill_lag`` bars of delay, so the *filled*
position visible via ``ctx.portfolio`` lags the decision by a bar. A robust
strategy therefore tracks its own intended target (not the lagged filled
position) and only emits orders when the target changes. This yields exactly
one entry and one exit for a single crossover, instead of oscillating.
"""

from __future__ import annotations

from backtester.core import BarContext, Order

FAST = 50
SLOW = 200
QTY = 100


class SMACrossover:
    """Long when SMA(50) > SMA(200), flat otherwise; rebalances to target."""

    def __init__(self) -> None:
        self._target: float = 0.0

    def on_bar(self, ctx: BarContext) -> list[Order]:
        fast = ctx.indicators.get("sma_50")
        slow = ctx.indicators.get("sma_200")
        if fast is None or slow is None:
            return []
        # Wait until both windows have enough history (prefix length == t + 1).
        if fast.t < SLOW:
            return []
        fast_val = fast.current()
        slow_val = slow.current()
        if fast_val != fast_val or slow_val != slow_val:  # NaN guard
            return []

        desired = QTY if fast_val > slow_val else 0.0
        if desired == self._target:
            return []
        delta = desired - self._target
        self._target = desired
        return [Order(symbol=ctx.bar.symbol, qty=delta)]


strategy = SMACrossover()

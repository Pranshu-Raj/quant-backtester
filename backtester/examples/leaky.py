"""Leak-failing example strategy — proves the engine refuses to backtest a leaky strategy.

Running this via ``bt run --strategy backtester.examples.leaky`` is *supposed*
to abort. ``on_bar`` reads one bar past the current bar (``t + 1``); the
no-look-ahead enforcement catches that and raises ``LookAheadError``, aborting
the run with no partial result. This is the demonstrable proof that look-ahead
bias is architecturally impossible here, not a matter of discipline.
"""

from __future__ import annotations

from typing import List

from backtester.core import Order


class LeakyStrategy:
    """Intentionally peeks into the future; exists only to demonstrate the abort."""

    def on_bar(self, ctx) -> List[Order]:  # noqa: ANN001 - ctx is BarContext
        window = ctx.indicators["sma_50"]
        # Reading beyond the current bar `t` is exactly the look-ahead the
        # engine hard-blocks. This line raises LookAheadError and aborts run().
        _ = window[window.t + 1]
        return []


strategy = LeakyStrategy()

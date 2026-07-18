"""Fill-price model for the engine.

The default and currently supported mode is ``next_close``: a signal generated
on bar ``t`` fills at the close of the bar ``fill_lag`` steps ahead (the
"next bar" when ``lag == 1``). At the end of the data there is no future bar,
so the model falls back to the signal bar's own close (it must never peek
beyond the data horizon to invent a price).
"""

from __future__ import annotations

from backtester.core import Bar

_SUPPORTED_MODES = ("next_close",)


class FillModel:
    """Resolves the execution price for a queued order."""

    def __init__(self, mode: str = "next_close", lag: int = 1) -> None:
        if mode not in _SUPPORTED_MODES:
            raise ValueError(
                f"unsupported fill mode {mode!r}; supported: {_SUPPORTED_MODES}"
            )
        if lag < 1:
            raise ValueError(f"fill lag must be >= 1, got {lag!r}")
        self.mode = mode
        self.lag = lag

    def price(self, current_bar: Bar, next_bar: Bar | None) -> float:
        """Return the fill price for ``current_bar``'s signal.

        ``next_bar`` is the bar ``lag`` steps ahead; when it is ``None`` (the
        signal occurs at or past the last available bar) the fill price falls
        back to ``current_bar.close`` rather than looking ahead past the data.
        """
        if next_bar is None:
            return current_bar.close
        return next_bar.close

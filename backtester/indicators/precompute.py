"""Per-symbol indicator precomputation for the engine.

This module is the **single** place the engine computes indicators. For each symbol
it vectorizes the standard indicator set once over the full price history and returns
the complete same-length series. The engine then slices the prefix ``[0..t]`` per bar
(``ctx.indicators_prefix``), so the indicators themselves never leak future data.

Pure and windowed: given the same bars, the output is deterministic with no side
effects and no mutation of the inputs.
"""

from __future__ import annotations

import pandas as pd

from .technical import bollinger, ema, macd, rolling_vol, rsi, sma


def precompute(bars_by_symbol: dict[str, pd.DataFrame]) -> dict[str, dict[str, pd.Series]]:
    """Compute the standard indicator set for every symbol.

    ``bars_by_symbol`` maps a symbol to a DataFrame that must contain a ``"close"``
    column (float). Returns ``{symbol: {name: pd.Series}}`` where every series has
    the same length and index as the symbol's input bars.

    The full series is returned; the engine slices the prefix per bar so no
    look-ahead is possible from this function.
    """
    result: dict[str, dict[str, pd.Series]] = {}

    for symbol, bars in bars_by_symbol.items():
        close = pd.Series(bars["close"], dtype="float64")

        indicators: dict[str, pd.Series] = {
            "sma_20": sma(close, 20),
            "sma_50": sma(close, 50),
            "sma_200": sma(close, 200),
            "ema_12": ema(close, 12),
            "ema_26": ema(close, 26),
            "rsi_14": rsi(close, 14),
        }

        macd_line, macd_signal, macd_hist = macd(close)
        indicators["macd"] = macd_line
        indicators["macd_signal"] = macd_signal
        indicators["macd_hist"] = macd_hist

        bb_mid, bb_upper, bb_lower = bollinger(close)
        indicators["bb_mid"] = bb_mid
        indicators["bb_upper"] = bb_upper
        indicators["bb_lower"] = bb_lower

        indicators["vol_20"] = rolling_vol(close, 20)

        result[symbol] = indicators

    return result

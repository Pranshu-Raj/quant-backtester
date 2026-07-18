"""Point-in-time data layer (PRINCIPLE 1 — no-look-ahead by construction).

Public surface:
    PITDataLoader     — enforces strictly time-ordered iteration
    CSVLocalAdapter    — loads bars from a local multi-symbol CSV
    AdjustmentPolicy   — back/forward splits & dividends at load time
    Universe           — re-exported from ``backtester.core`` for convenience
"""

from backtester.core import Universe
from backtester.data.adapters import AdjustmentPolicy, CSVLocalAdapter
from backtester.data.loader import PITDataLoader

__all__ = ["PITDataLoader", "CSVLocalAdapter", "AdjustmentPolicy", "Universe"]

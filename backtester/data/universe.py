"""Universe convenience helpers for the data layer."""

from __future__ import annotations

from datetime import date

from backtester.core import Universe


def date_range(universe: Universe) -> tuple[date, date]:
    """Return the inclusive ``(start, end)`` window of ``universe``.

    The values are plain ``date`` objects (the universe window is a calendar
    range, not a timestamp) so downstream code can compare without tz math.
    """
    return (universe.start, universe.end)

"""Concrete data adapters and the split/dividend adjustment policy.

``CSVLocalAdapter`` reads a local CSV of OHLCV bars (multi-symbol
capable) and returns timezone-aware UTC :class:`~backtester.core.Bar`
objects filtered to a universe. ``AdjustmentPolicy`` back- or
forward-adjusts OHLC at load time so the engine never has to.

Adjustment convention (per symbol, splits are per-symbol):
    f_t      = per-bar factor from ``split_ratio`` / ``dividend`` columns
    R_t      = product of f_j for j <= t            (cumulative factor)
    back:    price_t *= R_t / R_last   -> last bar unchanged
    forward: price_t *= R_t / R_first -> first bar unchanged
This yields a continuous series anchored at the chosen end (back) or
start (forward), which is the standard point-in-time behaviour.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Union

import pandas as pd

from backtester.core import Bar, Universe

_TS_COLUMN_CANDIDATES = ("ts", "date")
_REQUIRED_COLUMNS = ("symbol", "open", "high", "low", "close", "volume")
_NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume")


class CSVLocalAdapter:
    """Loads bars from a local CSV file.

    Expected columns: ``date`` (or ``ts``), ``symbol``, ``open``,
    ``high``, ``low``, ``close``, ``volume``. Optional corporate-action
    columns ``split_ratio`` / ``dividend`` are carried onto each
    :class:`~backtester.core.Bar` for :class:`AdjustmentPolicy`.
    """

    def __init__(self, path: Union[str, Path]) -> None:
        self._path = Path(path)

    def load(self, universe: Universe) -> list[Bar]:
        """Read, normalize, and filter the CSV to ``universe``."""
        if not self._path.exists():
            raise FileNotFoundError(f"CSV adapter path not found: {self._path}")

        frame = pd.read_csv(self._path)
        frame.columns = [str(c).strip().lower() for c in frame.columns]
        ts_column = self._resolve_ts_column(frame.columns)
        self._validate_columns(frame.columns, ts_column)
        frame = self._normalize(frame, ts_column)
        frame = self._filter_universe(frame, universe)
        return self._to_bars(frame)

    @staticmethod
    def _resolve_ts_column(columns: "pd.Index") -> str:
        for candidate in _TS_COLUMN_CANDIDATES:
            if candidate in columns:
                return candidate
        raise ValueError(
            f"CSV must contain a 'date' or 'ts' column; found columns: {list(columns)}"
        )

    @staticmethod
    def _validate_columns(columns: "pd.Index", ts_column: str) -> None:
        missing = [c for c in _REQUIRED_COLUMNS if c not in columns]
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")

    def _normalize(self, frame: pd.DataFrame, ts_column: str) -> pd.DataFrame:
        frame = frame.copy()
        frame[ts_column] = pd.to_datetime(frame[ts_column], utc=True, errors="raise")
        for col in _NUMERIC_COLUMNS:
            frame[col] = pd.to_numeric(frame[col], errors="raise").astype(float)
        frame["symbol"] = frame["symbol"].astype(str)
        frame = frame.rename(columns={ts_column: "ts"})
        return frame

    @staticmethod
    def _filter_universe(frame: pd.DataFrame, universe: Universe) -> pd.DataFrame:
        symbol_set = set(universe.symbols)
        start_ts = pd.Timestamp(universe.start, tz="UTC")
        # inclusive end: up to the last instant of the end date
        end_ts = (
            pd.Timestamp(universe.end, tz="UTC")
            + timedelta(days=1)
            - pd.Timedelta(nanoseconds=1)
        )
        mask = frame["symbol"].isin(symbol_set)
        mask &= frame["ts"] >= start_ts
        mask &= frame["ts"] <= end_ts
        return frame.loc[mask]

    def _to_bars(self, frame: pd.DataFrame) -> list[Bar]:
        has_split = "split_ratio" in frame.columns
        has_dividend = "dividend" in frame.columns
        if has_split:
            frame["split_ratio"] = pd.to_numeric(frame["split_ratio"], errors="coerce")
        if has_dividend:
            frame["dividend"] = pd.to_numeric(frame["dividend"], errors="coerce")

        bars: list[Bar] = []
        for row in frame.itertuples(index=False):
            extra = {}
            if has_split:
                sr = getattr(row, "split_ratio", None)
                extra["split_ratio"] = None if pd.isna(sr) else float(sr)
            if has_dividend:
                dv = getattr(row, "dividend", None)
                extra["dividend"] = None if pd.isna(dv) else float(dv)
            bars.append(
                Bar(
                    ts=row.ts.to_pydatetime(),
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    volume=float(row.volume),
                    symbol=str(row.symbol),
                    **extra,
                )
            )
        return sorted(bars, key=lambda b: (b.ts, b.symbol))


class AdjustmentPolicy:
    """Applies split/dividend adjustment to OHLC at load time.

    ``mode`` is ``"back"`` (anchor the most recent bar) or ``"forward"``
    (anchor the earliest bar). Pure: returns new :class:`Bar` objects and
    never mutates the input list.
    """

    VALID_MODES = ("back", "forward")

    def __init__(self, mode: str = "back") -> None:
        if mode not in self.VALID_MODES:
            raise ValueError(
                f"AdjustmentPolicy mode must be one of {self.VALID_MODES}, got {mode!r}"
            )
        self._mode = mode

    @property
    def mode(self) -> str:
        return self._mode

    def apply(self, bars: list[Bar]) -> list[Bar]:
        if not bars:
            return []

        by_symbol: dict[str, list[Bar]] = {}
        for bar in bars:
            by_symbol.setdefault(bar.symbol, []).append(bar)

        adjusted: list[Bar] = []
        for symbol_bars in by_symbol.values():
            adjusted.extend(self._adjust_symbol(symbol_bars))

        return sorted(adjusted, key=lambda b: (b.ts, b.symbol))

    def _adjust_symbol(self, bars: list[Bar]) -> list[Bar]:
        ordered = sorted(bars, key=lambda b: b.ts)
        factors = [self._bar_factor(b) for b in ordered]

        cumulative: list[float] = []
        running = 1.0
        for factor in factors:
            running *= factor
            cumulative.append(running)

        anchor = cumulative[0] if self._mode == "forward" else cumulative[-1]

        out: list[Bar] = []
        for bar, cum in zip(ordered, cumulative):
            scale = cum / anchor
            out.append(
                replace(
                    bar,
                    open=bar.open * scale,
                    high=bar.high * scale,
                    low=bar.low * scale,
                    close=bar.close * scale,
                )
            )
        return out

    @staticmethod
    def _bar_factor(bar: Bar) -> float:
        """Per-bar raw adjustment factor (1.0 when no action column present)."""
        if bar.split_ratio is not None:
            return float(bar.split_ratio)
        if bar.dividend is not None:
            if bar.close == 0:
                return 1.0
            return 1.0 - float(bar.dividend) / float(bar.close)
        return 1.0

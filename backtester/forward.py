"""Forward-validation orchestration (v0.5 Milestone 3).

``run_forward`` splits a universe into a contiguous, non-overlapping in-sample
leg and out-of-sample leg, runs the *same* strategy (a fresh instance per leg,
so no in-sample memory leaks forward) on each, and reports the gap. This is a
*reporting* check only: it never re-fits or re-selects parameters. Per the PRD,
v0.5 reports the in-sample vs out-of-sample gap and the user acts on it manually
(no optimizer).

Correctness guarantees enforced here:
- Fresh strategy instance per leg (strategies are stateful, e.g.
  ``SMACrossover._target``; reusing one instance would carry in-sample state
  into the out-of-sample leg — a forward leak).
- The out-of-sample leg is a single confirmatory run, so it is audited honestly
  at ``trials=1`` (no selection overfit); only the in-sample leg keeps the
  configured ``trials``.
- The two legs do not share a bar: in-sample is inclusive ``[start, split_date]``,
  out-of-sample is ``[split_date + 1 day, end]``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Tuple

from backtester.analytics.metrics import cagr, max_drawdown, sharpe, sortino
from backtester.core import (
    BacktestResult,
    Config,
    PITDataLoaderProtocol,
    StrategyProtocol,
    Universe,
)
from backtester.engine import run

# A leg with fewer equity points has no meaningful return distribution.
_MIN_BARS_PER_LEG = 2


@dataclass(frozen=True)
class ForwardGap:
    """Comparison of in-sample vs out-of-sample performance."""

    in_sample_sharpe: float
    out_of_sample_sharpe: float
    in_sample_sortino: float
    out_of_sample_sortino: float
    in_sample_cagr: float
    out_of_sample_cagr: float
    in_sample_max_drawdown: float
    out_of_sample_max_drawdown: float
    in_sample_deflated_sharpe: float
    out_of_sample_deflated_sharpe: float
    verdict: str
    notes: str

    def __post_init__(self) -> None:
        if self.verdict not in ("robust", "degraded", "failed"):
            raise ValueError(
                f"verdict must be 'robust', 'degraded', or 'failed', got {self.verdict!r}"
            )


@dataclass(frozen=True)
class ForwardResult:
    """Immutable outcome of a forward-validation run."""

    in_sample: BacktestResult
    out_of_sample: BacktestResult
    gap: ForwardGap
    split_date: date


def split_universe(
    loader: PITDataLoaderProtocol,
    universe: Universe,
    split: float = 0.6,
) -> Tuple[Universe, Universe, date]:
    """Split a universe into contiguous, non-overlapping in-sample / OOS legs.

    The split is computed from the **actual bars available** for ``universe``
    (not its declared date range — a config may declare an end date past the
    last row of data, in which case a date-based split would park the whole
    out-of-sample leg in empty territory). The split bar falls in the in-sample
    leg; the out-of-sample leg starts the next day, so the two legs are adjacent
    with no shared bar.

    Args:
        loader: Point-in-time loader for ``universe`` (used to discover the real
            timeline).
        universe: The full range to validate over.
        split: Fraction (exclusive of 0 and 1) of the bar count used as the
            in-sample leg; the remainder is the out-of-sample leg.

    Returns:
        ``(in_sample, out_of_sample, split_date)`` where ``in_sample`` ends on
        ``split_date`` and ``out_of_sample`` starts the day after.

    Raises:
        ValueError: If ``split`` is not in ``(0, 1)``, or there are too few bars
            to form a meaningful split (at least 2 bars per leg).
    """
    if split <= 0.0 or split >= 1.0:
        raise ValueError(f"split must be in (0, 1), got {split}")

    bars = list(loader.iter_bars(universe))
    n = len(bars)
    if n < 4:
        raise ValueError("forward validation needs at least 4 bars to split")

    # k = index of the last in-sample bar; clamp so each leg keeps >= 1 bar.
    k = int(round(split * (n - 1)))
    k = max(1, min(k, n - 2))
    if k + 1 < _MIN_BARS_PER_LEG or n - 1 - k < _MIN_BARS_PER_LEG:
        raise ValueError("forward validation needs at least 2 bars in each leg")

    split_date = bars[k].ts.date()
    in_sample = universe.model_copy(update={"end": split_date})
    out_of_sample = universe.model_copy(update={"start": split_date + timedelta(days=1)})
    return in_sample, out_of_sample, split_date


def _verdict(in_sample_sharpe: float, out_of_sample_sharpe: float) -> Tuple[str, str]:
    """Three-tier forward verdict from the Sharpe gap."""
    if out_of_sample_sharpe < 0:
        return "failed", "out-of-sample Sharpe is negative"
    if out_of_sample_sharpe < 0.5 * in_sample_sharpe:
        return "degraded", "out-of-sample Sharpe decayed >50% vs in-sample"
    return "robust", "out-of-sample performance held up vs in-sample"


def _safe_cagr(equity) -> float:
    """CAGR can raise on a non-positive curve; forward legs stay positive, but
    guard anyway so a reporting step never crashes on odd data."""
    try:
        return cagr(equity)
    except ValueError:
        return 0.0


def run_forward(
    config: Config,
    loader: PITDataLoaderProtocol,
    make_strategy: Callable[[], StrategyProtocol],
    split: float = 0.6,
) -> ForwardResult:
    """Run a forward-validation check: in-sample vs out-of-sample gap.

    The same strategy (fresh instance per leg) runs on two non-overlapping
    slices of the data. The in-sample leg keeps the configured ``trials``; the
    out-of-sample leg is a single confirmatory run audited at ``trials=1``.

    Args:
        config: Validated run configuration (its ``universe`` is split).
        loader: Point-in-time loader for the configured universe.
        make_strategy: Zero-arg factory returning a fresh strategy instance.
        split: In-sample fraction of the date span, in ``(0, 1)``.

    Returns:
        A :class:`ForwardResult` carrying both legs, the computed gap, and the
        split date.

    Raises:
        ValueError: If the split is invalid, the range too short, a leg yields
            too few bars, or a leg's strategy leaks (LookAheadError propagates
            from ``run`` — the no-look-ahead guarantee holds here too).
    """
    in_sample_u, out_of_sample_u, split_date = split_universe(loader, config.universe, split)

    is_cfg = config.model_copy(update={"universe": in_sample_u})
    # Out-of-sample is one confirmatory run: honest at trials=1 (no selection).
    oos_cfg = config.model_copy(update={"universe": out_of_sample_u, "trials": 1})

    is_res = run(is_cfg, loader, make_strategy())
    oos_res = run(oos_cfg, loader, make_strategy())

    if len(is_res.equity_curve) < _MIN_BARS_PER_LEG:
        raise ValueError("forward validation needs at least 2 bars in the in-sample leg")
    if len(oos_res.equity_curve) < _MIN_BARS_PER_LEG:
        raise ValueError("forward validation needs at least 2 bars in the out-of-sample leg")

    is_sharpe = sharpe(is_res.equity_curve)
    oos_sharpe = sharpe(oos_res.equity_curve)
    verdict, notes = _verdict(is_sharpe, oos_sharpe)

    gap = ForwardGap(
        in_sample_sharpe=is_sharpe,
        out_of_sample_sharpe=oos_sharpe,
        in_sample_sortino=sortino(is_res.equity_curve),
        out_of_sample_sortino=sortino(oos_res.equity_curve),
        in_sample_cagr=_safe_cagr(is_res.equity_curve),
        out_of_sample_cagr=_safe_cagr(oos_res.equity_curve),
        in_sample_max_drawdown=max_drawdown(is_res.equity_curve),
        out_of_sample_max_drawdown=max_drawdown(oos_res.equity_curve),
        in_sample_deflated_sharpe=is_res.audit.deflated_sharpe,
        out_of_sample_deflated_sharpe=oos_res.audit.deflated_sharpe,
        verdict=verdict,
        notes=notes,
    )
    return ForwardResult(
        in_sample=is_res, out_of_sample=oos_res, gap=gap, split_date=split_date
    )

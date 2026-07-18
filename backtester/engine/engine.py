"""The simulation core and the ENFORCEMENT POINT of the no-look-ahead guarantee.

``run`` walks bars in strict timestamp order. For each bar ``t`` it builds a
per-symbol :class:`~backtester.core.IndicatorWindow` that is hard-capped at
``t`` — any strategy that indexes beyond ``t`` triggers ``LookAheadError``
inside ``IndicatorWindow.__getitem__``, which propagates out of ``run`` and
aborts the backtest (no partial result is produced). This is Principle 1 of
``backtester-architecture.md``.

The engine integrates the real sibling modules: indicators are precomputed via
``backtester.indicators.precompute``, costs via ``get_cost_model``, and the
mandatory overfitting audit via ``backtester.audit.audit``.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd

from backtester.audit import audit
from backtester.core import (
    ENGINE_VERSION,
    BacktestResult,
    Bar,
    BarContext,
    Config,
    IndicatorWindow,
    Order,
    PITDataLoaderProtocol,
    StrategyProtocol,
    Trade,
    config_hash,
    data_hash,
)
from backtester.costs.registry import get_cost_model
from backtester.indicators.precompute import precompute

from .fill import FillModel
from .portfolio import Portfolio


def run(
    config: Config,
    loader: PITDataLoaderProtocol,
    strategy: StrategyProtocol,
) -> BacktestResult:
    """Execute a point-in-time backtest and return an immutable ``BacktestResult``.

    Args:
        config: Validated run configuration (universe, cash, fill/cost models).
        loader: A point-in-time loader yielding strictly ascending ``Bar`` rows.
        strategy: A ``StrategyProtocol`` conformer producing orders per bar.

    Returns:
        A :class:`~backtester.core.BacktestResult` carrying the equity curve,
        trade log, determinism manifest, and the mandatory ``AuditReport``.

    Raises:
        LookAheadError: If the strategy reads any indicator index ``> t``.
            This aborts the run with no partial result (the guarantee).
    """
    # 1. Gather bars (already ascending / point-in-time from the loader).
    bars: List[Bar] = list(loader.iter_bars(config.universe))
    if not bars:
        raise ValueError("loader yielded no bars for the configured universe")

    # 2. Precompute the per-symbol indicator series (full length; engine slices).
    frames: Dict[str, pd.DataFrame] = {}
    for symbol in {bar.symbol for bar in bars}:
        closes = [bar.close for bar in bars if bar.symbol == symbol]
        frames[symbol] = pd.DataFrame({"close": pd.Series(closes, dtype="float64")})
    indicator_series: Dict[str, Dict[str, pd.Series]] = precompute(frames)

    # Per-symbol index ``t`` for each global bar (so the window length is t+1).
    per_symbol_t: List[int] = []
    seen: Dict[str, int] = {}
    for bar in bars:
        t = seen.get(bar.symbol, -1) + 1
        seen[bar.symbol] = t
        per_symbol_t.append(t)

    # 3. Walk bars in ``t`` order.
    portfolio = Portfolio(config.starting_cash)
    cost_model = get_cost_model(config.cost_model, config.cost_params)
    fill_model = FillModel(mode=config.fill_model, lag=config.fill_lag)

    # Pending fills: (global fill index, order, signal bar).
    pending: List[Tuple[int, Order, Bar]] = []
    equity_index: List[object] = []
    equity_values: List[float] = []
    trades: List[Trade] = []

    n = len(bars)
    for g, bar in enumerate(bars):
        t = per_symbol_t[g]

        # Build the no-look-ahead indicator windows for this bar's symbol.
        windows: Dict[str, IndicatorWindow] = {}
        sym_series = indicator_series.get(bar.symbol, {})
        for name, series in sym_series.items():
            prefix = series.iloc[0 : t + 1].tolist()
            windows[name] = IndicatorWindow(prefix, t)

        ctx = BarContext(
            bar=bar,
            indicators=windows,
            portfolio=portfolio.snapshot(bar),
        )

        orders = strategy.on_bar(ctx) or []
        for order in orders:
            pending.append((g + config.fill_lag, order, bar))

        # Execute any fills that come due at this global index.
        still_pending: List[Tuple[int, Order, Bar]] = []
        for fill_index, order, signal_bar in pending:
            if fill_index <= g:
                next_bar = bars[fill_index] if fill_index < n else None
                fill_price = fill_model.price(signal_bar, next_bar)
                cost = cost_model.apply(fill_price, order.qty)
                fill_bar = signal_bar if next_bar is None else next_bar
                trade = portfolio.apply(fill_bar, order.qty, fill_price, cost)
                trades.append(trade)
            else:
                still_pending.append((fill_index, order, signal_bar))
        pending = still_pending

        equity_index.append(bar.ts)
        equity_values.append(portfolio.equity_at(bar))

    # Orders that could not fill inside the data window fill at data end
    # (next_bar is None -> FillModel falls back to the signal bar's close).
    for _fill_index, order, signal_bar in pending:
        fill_price = fill_model.price(signal_bar, None)
        cost = cost_model.apply(fill_price, order.qty)
        trade = portfolio.apply(signal_bar, order.qty, fill_price, cost)
        trades.append(trade)

    equity_curve = pd.Series(
        equity_values, index=pd.Index(equity_index, name="ts")
    )

    # Determinism manifest + mandatory audit (Principle 5).
    chash = config_hash(config)
    dhash = data_hash(bars)
    report = audit(equity_curve, trials=config.trials)

    return BacktestResult(
        equity_curve=equity_curve,
        trades=trades,
        config_hash=chash,
        data_hash=dhash,
        engine_version=ENGINE_VERSION,
        audit=report,
    )

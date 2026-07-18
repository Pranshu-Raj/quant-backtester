"""Command-line interface for the backtester.

This module is the ``bt`` console entry point. It maps a YAML config onto the
``Config`` model, builds the point-in-time data loader, loads the strategy,
runs the (pure, no-look-ahead) engine, and prints the tearsheet + audit.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import typer
import yaml

app = typer.Typer(
    help="Stock-only backtester with a no-look-ahead-by-default engine.",
    add_completion=False,
)


def _load_strategy(module_path: str):
    """Import ``module_path`` and return its ``strategy`` instance (or ``Strategy()``)."""
    try:
        mod = importlib.import_module(module_path)
    except ImportError as exc:
        typer.echo(f"could not import strategy module {module_path!r}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    strat = getattr(mod, "strategy", None)
    if strat is None and hasattr(mod, "Strategy"):
        strat = mod.Strategy()
    if strat is None:
        typer.echo(
            f"{module_path!r} must expose a `strategy` instance or a `Strategy` class",
            err=True,
        )
        raise typer.Exit(code=1)
    return strat


@app.command()
def run(
    config: Path,
    out: str = typer.Option(None, "--out", help="Persist a run manifest under this id."),
    strategy: str = typer.Option(
        "backtester.examples.sma_crossover",
        "--strategy",
        help="Importable module exposing a `strategy` instance (StrategyProtocol).",
    ),
) -> None:
    """Run a backtest from a YAML config file."""
    if not config.exists():
        typer.echo(f"config not found: {config}", err=True)
        raise typer.Exit(code=1)

    from backtester.core import Config

    raw = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    parsed = Config.model_validate(raw)

    typer.echo(
        f"loaded config for {len(parsed.universe.symbols)} symbols, "
        f"{parsed.universe.start}..{parsed.universe.end}"
    )

    from backtester.analytics import print_tearsheet
    from backtester.data import AdjustmentPolicy, CSVLocalAdapter, PITDataLoader
    from backtester.engine import run as run_backtest

    adapter = CSVLocalAdapter(path=parsed.data_path)
    adjustment = AdjustmentPolicy(mode=parsed.adjustment) if parsed.adjustment else None
    loader = PITDataLoader(adapter=adapter, adjustment=adjustment)

    strat = _load_strategy(strategy)
    result = run_backtest(parsed, loader, strat)

    typer.echo(print_tearsheet(result))

    if out:
        run_dir = Path.home() / ".backtester" / "runs" / out
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "run_id": out,
            "config_hash": result.config_hash,
            "data_hash": result.data_hash,
            "engine_version": result.engine_version,
            "audit": {
                "verdict": result.audit.verdict,
                "deflated_sharpe": result.audit.deflated_sharpe,
            },
            "n_trades": len(result.trades),
            "final_equity": float(result.equity_curve.iloc[-1]),
        }
        (run_dir / "result.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        typer.echo(f"manifest written to {run_dir / 'result.json'}")


if __name__ == "__main__":
    app()

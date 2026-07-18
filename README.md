# backtester

A stock-only backtesting platform with a **no-look-ahead-by-default** engine.

The core library is pure and deterministic (`config + data -> result`): strategies can only
ever see state up to the current bar, so look-ahead bias is architecturally impossible rather
than a matter of discipline. Every result ships with a mandatory overfitting audit.

## Install

```bash
pip install -e .
```

## Usage

```bash
bt --help
bt run --config cfg.yaml
bt run --config cfg.yaml --out run1
```

The `bt run` command loads a YAML config (mapped 1:1 onto the `Config` model), builds the
point-in-time data loader, runs the backtest, and prints the tearsheet + audit verdict.

> v0.1 is the pure library + CLI. The database, HTTP API, and web UI described in
> `ARCHITECTURE.md` are target layers built in later phases.

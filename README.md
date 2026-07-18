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
bt demo                          # zero-setup sample backtest (bundled data + config)
bt run --config cfg.yaml         # your own config
bt run --config cfg.yaml --out run1
```

`bt demo` runs a bundled sample end-to-end with no local files — a stranger can get a
trustworthy tearsheet in under five minutes after `pip install`. `bt run --config` loads a
YAML config (mapped 1:1 onto the `Config` model), builds the point-in-time data loader,
runs the backtest, and prints the tearsheet + audit verdict.

## Trust by architecture

Look-ahead bias is impossible by construction, not discipline. A strategy can only ever
read indicator state up to the current bar `t`; reading `t + 1` raises `LookAheadError`
and aborts the run with **no partial result**. See it fail on purpose:

```bash
bt run --strategy backtester.examples.leaky
# -> LookAheadError: the engine refuses to backtest a leaky strategy
```

Every run also emits the **mandatory overfitting audit** — Deflated Sharpe, the
backtest-overfitting probability (PBO), and a `pass`/`warn` verdict — so you can read
exactly how much to trust the result before risking capital.

> v0.5 is the installable, trust-visible wedge. The database, HTTP API, web UI, and
> empirical PBO described in `ARCHITECTURE.md` are target layers built in later phases.

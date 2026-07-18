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
bt validate                      # forward check: in-sample vs out-of-sample gap
bt validate --split 0.7         # customize the in-sample fraction
bt web                          # minimal localhost web UI (no new dependencies)
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

### Forward check

`bt validate` runs the **forward-validation mode**: it splits the data into an
in-sample leg and a held-out out-of-sample leg, runs the *same* strategy on both,
and reports the gap (CAGR / Sharpe / Sortino / Max Drawdown / Deflated Sharpe) with a
`robust` / `degraded` / `failed` verdict. This is the core trust test — does the
strategy hold up on data it never saw? Reporting only: it never re-fits the
strategy. A leaky strategy still hard-aborts with `LookAheadError`.

### Web UI

`bt web` starts a minimal, **zero-dependency** web UI at `http://127.0.0.1:8000`
(built on the Python stdlib `http.server` — no new packages to install). A single
page lets you pick **Run** (backtest + audit) or **Validate** (forward check), run
the **bundled sample with no files**, paste an inline strategy, or upload a CSV.
The result — tearsheet, audit verdict, or the forward-check report — renders inline.

```bash
bt web                          # serve at http://127.0.0.1:8000
bt web --port 8731             # pick a port
```

> **Trust boundary — read this.** `bt web` binds to `127.0.0.1` only and is meant
> for a **single, trusted, local user** (the v0.5 single-user model; a real
> multi-user server with auth is a v1.0+ concern). It **executes any strategy code
> you paste** and reads uploaded CSV files. That is arbitrary local code/file
> execution — safe *only* because it is localhost and single-user. Do not expose it
> to a network or untrusted users, and there is no sandboxing. All errors are caught
> and shown on the page, so the server never crashes on bad input. The `--host`
> option is locked to loopback addresses (`127.0.0.1`, `::1`, `localhost`); any
> other host is refused.

> v0.5 is the installable, trust-visible, forward-validated, web-accessible wedge.
> The database, full HTTP API, and empirical PBO described in `ARCHITECTURE.md` are
> target layers built in later phases.

# Sprints

> **Purpose:** Break the roadmap into buildable sprints with explicit done-definitions. v0.1 is detailed sprint-by-sprint (the immediate build); later phases list sprint *themes*.
> **Assumptions (E1–E6 defaults):** DuckDB+Parquet analytical, SQLite→Postgres metadata, React+Vite, FastAPI, auth at v1.0, CLI-only at v0.1.
> **Cadence:** 1-week sprints for v0.1 (solo founder); adjust as needed.

---

## v0.1 — Personal Tool (detailed)

### S0 · Scaffold & Tooling
- **Goal:** a runnable, testable package skeleton.
- **Scope:** `pyproject.toml`, src layout `backtester/`, pytest + ruff + mypy, pre-commit, `backtester/architecture.md` reference.
- **Deliverables:** repo runs `pytest` green (empty), `bt` entry point prints help.
- **Done when:** `pip install -e .` works; `pytest` passes; `bt --help` shows.
- **Depends on:** none.

### S1 · Core Contracts
- **Goal:** the immutable contracts everything depends on.
- **Scope:** `core/` — `Bar`, `Trade`, `BacktestResult` (frozen dataclasses), pydantic `Config`, `StrategyProtocol`, `BarContext`, `LookAheadError`.
- **Deliverables:** typed contracts + unit tests for validation.
- **Done when:** invalid `Config` raises field errors; `BarContext` has **no** future-access method.
- **Depends on:** S0.

### S2 · Data Layer (PIT)
- **Goal:** point-in-time data access by construction.
- **Scope:** `data/` — `PITDataLoader` iface, `iter_bars()` (ascending), `CSVLocalAdapter`, `AdjustmentPolicy`, `Universe`.
- **Deliverables:** loader + adapter + adjustment + universe, with fixtures.
- **Done when:** shuffled input yields ascending bars; split-adjust matches reference; `LookAheadError` impossible via the iterator.
- **Depends on:** S1.

### S3 · Indicators & Signals
- **Goal:** vectorized, leak-free indicators.
- **Scope:** `indicators/` — `sma, ema, rsi, macd, bollinger, rolling_vol, cross`, signal primitives, per-symbol precompute.
- **Deliverables:** indicator lib + precompute + tests vs reference.
- **Done when:** each indicator matches reference; `cross` fires only on cross bar; precompute prefix equals full recompute.
- **Depends on:** S1.

### S4 · Engine Core
- **Goal:** the enforcement point — t-ordered simulation with no look-ahead.
- **Scope:** `engine/` — `run()`, timestamp loop, next-bar-close `FillModel`, `Portfolio`, market + target-weight orders, `LookAheadError` hard-abort.
- **Deliverables:** engine + loop + fill + portfolio + leak test harness.
- **Done when:** a strategy reading `t+1` aborts with `LookAheadError` and emits no partial result; known trade sequence reproduces hand-computed equity.
- **Depends on:** S1, S2, S3.

### S5 · Cost Models
- **Goal:** pluggable costs.
- **Scope:** `costs/` — `BaseCostModel` iface, `FlatPerTrade`.
- **Deliverables:** interface + one model + test.
- **Done when:** commission deducted exactly; custom model drops in with no core edit.
- **Depends on:** S4.

### S6 · Analytics
- **Goal:** the tearsheet metrics.
- **Scope:** `analytics/` — CAGR, Sharpe, Sortino, Calmar, MaxDD, trade/exposure stats, cost attribution.
- **Deliverables:** metrics + tests vs reference.
- **Done when:** each metric matches reference on a fixture curve; net = gross − attributed cost.
- **Depends on:** S4.

### S7 · Overfitting Audit
- **Goal:** mandatory trust audit.
- **Scope:** `audit/` — Deflated Sharpe; `audit(result)` always attached; cannot be disabled via config.
- **Deliverables:** audit module + enforced-attachment test.
- **Done when:** removing the call fails a test; config flag can't disable it.
- **Depends on:** S4, S6.

### S8 · CLI
- **Goal:** one command end-to-end.
- **Scope:** `cli.py` — `bt run --config <file>`, loads config+data, runs, prints tearsheet + audit, writes run manifest.
- **Deliverables:** CLI + example `config.yaml` + sample CSV.
- **Done when:** `bt run -c cfg.yaml` prints metrics + audit + writes `~/.backtester/runs/<id>/`.
- **Depends on:** S1–S7.

### S9 · Reference Strategy & Repro
- **Goal:** prove the whole pipeline with a real strategy.
- **Scope:** SMA-crossover strategy using `indicators` + `StrategyProtocol`; determinism check (same manifest ⇒ identical equity).
- **Deliverables:** `examples/sma_crossover.py` + repro test.
- **Done when:** SMA strategy runs via CLI; re-run with same manifest yields byte-identical `equity_curve`.
- **Depends on:** S8.

**v0.1 Exit (Done when ALL):** a stranger clones the repo, supplies a CSV + config, runs `bt run`, and gets a trustworthy tearsheet + audit in < 5 minutes, with no UI required.

---

## v0.5 — Launch-Worthy Wedge (themes)
- **S10 API & Storage** — FastAPI run lifecycle; DuckDB analytical + SQLite metadata stores.
- **S11 Web Frontend v1** — Dashboard, Strategy Editor, Run Launcher, Tearsheet Viewer, Audit/Trust view (React+Vite).
- **S12 Packaging & Examples** — `pip install backtester`; 3 leak-failing example strategies; HTML tearsheet; strategy templates.
- **Exit:** a stranger runs a trustworthy backtest from the web UI in 5 min; the 3 examples fail loudly if edited to leak.

## v1.0 — Community (themes)
- **S13 Auth & Multi-user** — FastAPI auth; Postgres metadata.
- **S14 Compute & Data Pipeline** — job workers; `POST /datasets/ingest`; plugin data interface.
- **S15 CI Audit Gate & Upstream** — audit gate blocks warn PRs; contribute broker/adapter shims.
- **Exit:** community contributes a working data adapter; CI enforces the no-look-ahead audit.

## v2.0 — Sustainability (themes)
- **S16 Hosted Compute** — scaled workers; cloud columnar + hosted PG; observability.
- **S17 Monetization** — paid PIT data tier; hosted compute tier; billing; open-core split.
- **S18 Ecosystem** — adapter marketplace; shareable trust certificates; public trust score.
- **Exit:** a paid user runs a heavy sweep on hosted compute with subscribed PIT data.

---

## Dependency graph (v0.1)
```
S0 → S1 → S2 ┐
             ├→ S4 → S5 → S6 → S7 → S8 → S9
S0 → S1 → S3 ┘
```
S2 and S3 are independent; S4 is the merge point.

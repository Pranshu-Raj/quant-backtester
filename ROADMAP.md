# Roadmap

> **Vision:** A stock-only backtesting platform that is **trustworthy by architecture** — it is structurally impossible to produce a look-ahead-biased or overfit result. Starts as a personal research tool; becomes an open-source product with a free engine and paid data/hosting.
>
> **Wedge (the differentiator):** *No-look-ahead by default, architecturally enforced* + a mandatory overfitting audit on every result. The engine refuses to lie to you.

---

## Phase Overview

| Phase | Identity | Audience | Money model |
|-------|----------|----------|-------------|
| **v0.1** | Personal tool | You (solo) | free (self) |
| **v0.5** | Launch-worthy wedge | Strangers / early users | free (OSS) |
| **v1.0** | Community | Contributors + multi-user | free + optional |
| **v2.0** | Sustainability | Paid users | engine free · data/hosting paid |

---

## v0.1 — Personal Tool
- **Theme:** prove the engine + the guarantee, locally, no UI.
- **Must-have:** pure core lib (data/indicators/engine/costs/analytics/audit), CLI, PIT CSV loader, SMA example, run manifest, local Parquet cache.
- **Explicitly out:** API, database server, web UI, auth, packaging on PyPI, live trading.
- **Launch trigger:** *a stranger runs one trustworthy backtest from the CLI in < 5 min.*
- **Success metric:** you trust the numbers enough to act on a strategy decision.
- **Risk:** over-building UI before the core is trusted → mitigated by CLI-only scope.

## v0.5 — Launch-Worthy Wedge
- **Theme:** make the trust guarantee *demonstrable to others*.
- **Must-have:** `pip install backtester`; FastAPI + run lifecycle; DuckDB analytical + SQLite metadata; React SPA (Dashboard/Editor/Launcher/Tearsheet/Audit); HTML tearsheet; 3 leak-failing example strategies; Deflated Sharpe + PBO audit surfaced.
- **Launch trigger:** *a stranger runs a trustworthy backtest from the web UI in 5 min, and the 3 examples fail loudly if edited to peek forward.*
- **Success metric:** external user reproduces a result you published; audit badge is trusted.
- **Risk:** scope creep in the web app → mitigated by fixing the 5 v0.5 pages only.

## v1.0 — Community
- **Theme:** let others extend it.
- **Must-have:** auth + Postgres; job workers for sweeps; data-pipeline API; plugin data interface; CI audit gate (warn PRs blocked); contribute broker/adapter shims upstream.
- **Launch trigger:** *a community contributor ships a working data adapter via the plugin interface, and CI rejects an overfit PR.*
- **Success metric:** ≥ 1 external adapter merged; repeatable multi-user runs.
- **Risk:** maintainer burnout from contributions → mitigated by tight interface contracts + CI gates.

## v2.0 — Sustainability
- **Theme:** turn trust into a business without charging for the calculator.
- **Must-have:** hosted compute (scaled workers, cloud columnar + hosted PG); paid PIT data tier; hosted-compute tier; billing; open-core split; adapter marketplace; shareable trust certificates.
- **Launch trigger:** *a paid user runs a heavy sweep on hosted compute using subscribed PIT data.*
- **Success metric:** recurring revenue from data + compute while the engine stays free/OSS.
- **Risk:** data-vendor margin pressure → mitigated by owning the PIT loader + multi-vendor adapters.

---

## Strategic Principles (constant across phases)
1. **Engine free, data/hosting paid** — never monetize the calculator.
2. **Wrap, don't fork** — reuse vectorbt/nautilus/LEAN where helpful; own the contracts, the no-look-ahead guarantee, the audit, the reporting.
3. **Smallest trustworthy surface first** — v0.1 is deliberately tiny; trust compounds.
4. **Every result is audited** — no exceptions, no config escapes.
5. **Reproducible by manifest** — same `config_hash + data_hash + seed` ⇒ identical output.

## Biggest Exploitable OSS Gaps (where we win)
- Clean **point-in-time, survivorship-free equities data** (vendor-only in production).
- A **production-grade risk engine** (no Barra-style OSS).
- A backtester that leads with **architectural no-look-ahead trust**, not feature count.

## Decision Log (carried from architecture)
- E1 Analytical store: **DuckDB + Parquet**. E2 Metadata: **SQLite → Postgres**. E3 Frontend: **React + Vite**. E4 API: **FastAPI**. E5 Auth: **v1.0**. E6 v0.1 UI: **CLI-only**.
- MVP settings (D1–D5): **daily bars · local CSV · SMA crossover · ~30 names / 5 yrs · pandas** (recommendations; configurable).

# Project Architecture — Database, Backend & Frontend

> **Scope note:** Originally scoped as a backend-only *pure* library (see `backtester-architecture.md`). This document expands that to the **whole project**: a data store, a backend service/API, and a frontend. v0.1 keeps the core library local; the DB/API/UI layers are specified here and built up across phases so we don't re-architect later.
>
> **Source of truth for the no-look-ahead guarantee & engine internals:** `backtester-architecture.md`. This doc describes how DB + backend + frontend *wrap* that core.

---

## 1. Target Architecture (overview)

```
┌──────────────────────────────────────────────────────────────────┐
│  FRONTEND  (web SPA)                                              │
│  Dashboard · Strategy Editor · Run Launcher · Tearsheet Viewer    │
│  Audit/Trust badge · (later) Data Manager · Account              │
└───────────────────────────┬──────────────────────────────────────┘
                             │  HTTPS / JSON  (typed API client)
┌───────────────────────────▼──────────────────────────────────────┐
│  BACKEND — API & ORCHESTRATION  (FastAPI)                         │
│  Auth (later) · Run lifecycle · Job scheduling · Result serving   │
└─────────┬───────────────────────────────────────┬────────────────┘
          │                                        │
┌─────────▼──────────┐                  ┌──────────▼──────────────┐
│  CORE LIBRARY       │                  │  DATA PIPELINE          │
│  (pure, no I/O)     │                  │  ingest → normalize →   │
│  data · indicators  │                  │  PIT store → adjust     │
│  engine · costs     │                  └──────────┬──────────────┘
│  analytics · audit  │                             │
└─────────┬──────────┘                  ┌──────────▼──────────────┐
          │                            │  DATABASE                │
┌─────────▼────────────────────────────▼──────────────────────────┐
│  ANALYTICAL STORE (DuckDB + Parquet)  │  METADATA STORE (SQLite→PG)│
│  bars · equity_curves · trades         │  users · strategies · runs │
│                                         │  configs · audits · datasets│
└──────────────────────────────────────────────────────────────────┘
```

**Key rule:** the **core library stays pure** (`config + data → result`, deterministic, no network). The API and frontend are *orchestration & presentation* layers that call the core. This keeps the trust guarantee intact no matter how the UI evolves.

---

## 2. Database Architecture

### 2.1 Two-store strategy (don't force one DB to do both jobs)

| Store | Engine (v0.1 → later) | Holds | Access pattern |
|-------|----------------------|-------|----------------|
| **Analytical** | Parquet files + **DuckDB** query layer → later cloud columnar | Time series: PIT bars, equity curves, trades | Bulk scan / range queries / analytics |
| **Metadata** | **SQLite** (single-file) → **Postgres** when web/multi-user | Strategies, configs, run registry, audits, datasets, users | Row lookups, relational, transactional |

Why split: price data is append-heavy columnar OLAP (DuckDB/Parquet is ideal); strategies/runs/users are relational OLTP (SQLite/Postgres). Mixing them in one engine causes pain later.

### 2.2 Analytical store — schema sketch

```
universes(universe_id PK, name, created_at)
symbols(symbol PK, universe_id FK, first_date, last_date)
bars(                                   -- partitioned by symbol/date
    symbol FK, ts, open, high, low, close, volume, adj_factor
)
equity_curves(run_id FK, ts, equity, drawdown)
trades(run_id FK, trade_id, ts, symbol, qty, fill_price, commission, slippage)
```
- Bars stored **columnar, partitioned** for fast range scans. Adjusted via `adj_factor` so raw + adjusted both recoverable.
- Every dataset carries a `data_hash` + `source` + `as_of_ts` for point-in-time provenance.

### 2.3 Metadata store — schema sketch

```
users(user_id PK, email, created_at)                       -- v1.0+
strategies(strategy_id PK, user_id FK, name, code_hash, created_at)
configs(config_id PK, strategy_id FK, config_json, config_hash)
runs(run_id PK, config_id FK, status, started_at, finished_at,
     engine_version, seed, config_hash, data_hash)         -- determinism manifest
audits(audit_id PK, run_id FK, deflated_sharpe, pbo, verdict)
datasets(dataset_id PK, name, adapter, universe_id FK, data_hash, as_of_ts)
```
- `runs` is the **provenance ledger**: re-running with the same `config_hash`+`data_hash`+`seed` must reproduce the same `equity_curves`/`trades`. This is what makes results auditable.

### 2.4 Versioning & migrations
- Analytical: immutable partitions + append; schema evolution via file-version metadata.
- Metadata: lightweight migration tool (e.g. Alembic for Postgres; manual for SQLite v0.1).

---

## 3. Backend Architecture

### 3.1 Core library (pure — unchanged from `backtester-architecture.md`)
`data / indicators / engine / costs / analytics / audit / core`. No DB, no network, no globals. This is where the no-look-ahead guarantee lives.

### 3.2 API & orchestration layer (FastAPI) — *new*
Thin wrapper that serves the frontend and persists results.

| Endpoint | Purpose | Phase |
|----------|---------|-------|
| `POST /runs` | submit config + strategy → create run, return `run_id` | v0.5 |
| `GET /runs/{id}` | poll status / fetch result + audit | v0.5 |
| `GET /strategies`, `POST /strategies` | manage strategies | v0.5 |
| `POST /datasets/ingest` | trigger data pipeline | v1.0 |
| `GET /tearsheet/{run_id}` | structured + HTML report | v0.5 |
| `POST /auth/*` | login/register | v1.0 |

- **Run lifecycle:** accept → validate config (pydantic) → load data from analytical store → call core `run()` → persist `equity_curves`/`trades`/`audits` to stores → mark finished.
- **Sync vs async:** v0.5 runs in-process and returns when done (small universes). v1.0+ uses a **job queue + workers** for long sweeps.

### 3.3 Compute / job layer
- v0.1–v0.5: in-process, single run.
- v1.0: background worker pool (e.g. Celery/ARQ) for sweeps.
- v2.0: hosted, horizontally-scaled compute (open-core paid).

### 3.4 No-look-ahead across the API
The API never passes future data to the core — it only loads the requested historical window; the core's own enforcement (t-ordered loop, `LookAheadError`) is the backstop. The audit runs server-side on every result.

---

## 4. Frontend Architecture

### 4.1 Stack recommendation
**React + TypeScript + Vite**, charting via **Lightweight Charts / Recharts**, state via **TanStack Query (server) + Zustand (client)**. SPA talking to the FastAPI via a typed client. (Next.js is an alternative if we want SSR/SEO later; SPA is simpler for a tool-style app.)

### 4.2 Feature / page map
| Page | Purpose | Phase |
|------|---------|-------|
| Dashboard | recent runs, trust scores, quick stats | v0.5 |
| Strategy Editor | write/edit strategy (code or form), validate | v0.5 |
| Run Launcher | pick strategy + universe + date range → launch | v0.5 |
| Tearsheet Viewer | equity curve, drawdown, metrics, trade table | v0.5 |
| Audit / Trust view | Deflated Sharpe, PBO, pass/warn badge | v0.5 |
| Data Manager | ingest/inspect datasets (PIT provenance) | v1.0 |
| Account / Settings | auth, billing (later) | v1.0+ |

### 4.3 Architecture inside the SPA
- **API client** (typed fetch wrapper, generated from backend schemas).
- **Server state:** TanStack Query (caching, polling run status).
- **Client state:** Zustand for editor/session UI state.
- **Design direction:** intentional, opinionated dashboard — not a default template. Hierarchy via scale, real data-viz treated as a first-class surface, semantic HTML, designed hover/focus states. (Follows the project's web design-quality bar.)

---

## 5. Cross-Cutting Concerns
- **Security:** validate all input at API boundary (pydantic); no secrets in code (env/secret manager); auth + rate-limiting at v1.0; CSP on the web app.
- **Determinism & provenance:** every run persisted with `config_hash + data_hash + engine_version + seed`; re-run by manifest.
- **No-look-ahead:** enforced in core; audited on every result; surfaced as a trust badge in UI.
- **CI/CD:** pytest (unit + leak tests) + audit gate; frontend type-check/build; backend lint.
- **Observability:** structured run logs, audit trail, result provenance.

---

## 6. End-to-End Data Flow (example)
```
1. User edits strategy in Strategy Editor → POST /strategies
2. User clicks "Run" with universe + range → POST /runs
3. API validates config, loads PIT bars from analytical store
4. Core engine runs (t-ordered, next-bar-close fills, costs) → BacktestResult
5. audit(result) computed server-side → AuditReport
6. equity_curves / trades / audits persisted to stores; run marked finished
7. Frontend polls GET /runs/{id} → renders Tearsheet + Trust badge
```

---

## 7. Phasing (what gets built when)

| Phase | Database | Backend | Frontend |
|-------|----------|---------|----------|
| **v0.1** | Parquet cache + SQLite (local, minimal) | Pure core lib + **CLI only** (no API) | **none** (CLI-driven) |
| **v0.5** | DuckDB analytical + SQLite metadata | FastAPI + run lifecycle + result serving | SPA: Dashboard, Editor, Launcher, Tearsheet, Audit |
| **v1.0** | Postgres metadata + plugin data iface | Auth + job workers + data pipeline API | + Data Manager, Account |
| **v2.0** | Cloud columnar + hosted PG | Hosted compute (scaled workers) | Billing, marketplace, shareable trust certs |

> **Note:** v0.1 has **no frontend and no API** — it's the pure library + CLI from the earlier doc. The DB/API/UI layers above are the *target* we build toward. This keeps the first build fast while the architecture is already drawn.

---

## 8. Open Decisions for this expanded scope
| # | Decision | Options | My default |
|---|----------|---------|------------|
| E1 | Analytical store engine | DuckDB+Parquet / Postgres columnar / ClickHouse | **DuckDB + Parquet** (zero-ops, fast) |
| E2 | Metadata store (v1.0+) | SQLite / Postgres | **SQLite now → Postgres at v1.0** |
| E3 | Frontend framework | React+Vite / Next.js / Svelte | **React + TypeScript + Vite** |
| E4 | API framework | FastAPI / Django / Flask | **FastAPI** (async, typed, natural for Python core) |
| E5 | Auth timing | v0.1 single-user / v1.0 multi-user | **single-user until v1.0** |
| E6 | v0.1 UI? | CLI-only / minimal web | **CLI-only** (keep first build lean) |

All are layer choices that don't touch the core engine or the no-look-ahead guarantee.

---

*Next docs to write: `FEATURES.md` (epic list + acceptance), `SPRINTS.md` (v0.1 sprint breakdown), `ROADMAP.md` (phased plan + launch triggers), `API.md` (endpoint + schema reference).*

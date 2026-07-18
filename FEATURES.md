# Features

> **Status:** Feature catalog for the stock-only backtesting platform.
> **Companion docs:** `ARCHITECTURE.md` (how it's built), `SPRINTS.md` (build order), `ROADMAP.md` (phasing), `API.md` (exact interfaces).
> **Legend:** `[v0.1]` build-now core · `[v0.5]` launch wedge · `[v1.0]` community · `[v2.0]` business. Every feature lists a **Done when** acceptance test.

---

## A. Data & Point-in-Time Layer
- **[v0.1] Strictly-ordered bar iterator** — `iter_bars()` yields bars in strictly ascending `ts`; adapters cannot reorder. *Enforcement #1 of no-look-ahead.* Done when: a test feeding shuffled bars still yields them ascending, and a descending adapter raises.
- **[v0.1] Local CSV adapter** — load adjusted OHLCV from user CSV; PIT-correct by construction. Done when: a sample CSV loads to `bars` with correct dtypes and ascending index.
- **[v0.1] Adjustment policy** — splits/dividends applied at load via `AdjustmentPolicy` (back- or forward-adjust); engine never adjusts. Done when: a split-adjusted series matches a known-good reference within 1e-6.
- **[v0.1] Universe definition** — typed list of symbols + date range; single source of "what we test." Done when: `Universe(["A","B"], "2019","2024")` validates and rejects bad symbols/dates.
- **[v0.5] Yahoo adapter (research_only)** — free download, flagged non-PIT-safe. Done when: loads data and the run is tagged `data_provenance=research`.
- **[v1.0] Plugin adapter registry** — third parties register sources via interface. Done when: a community adapter loads without core changes.
- **[v1.0] PIT fundamentals (optional)** — corporate-actions/fundamentals feed. Done when: a fundamental field is joinable to bars at correct `as_of_ts`.
- **[v2.0] Paid PIT data marketplace** — production survivorship-free equities. Done when: subscribed user streams a PIT dataset into the analytical store.

## B. Indicators & Signals
- **[v0.1] Vectorized indicator library** — `sma, ema, rsi, macd, bollinger, rolling_vol, cross`. Pure, windowed. Done when: each matches a reference implementation on a fixture.
- **[v0.1] Signal primitives** — `threshold, cross, rank` helpers → boolean/weighted signals at `t`. Done when: `cross(fast,slow)` fires only on the bar the cross occurs.
- **[v0.1] Per-symbol precompute** — indicators computed once vectorized, sliced per bar for engine. Done when: precompute output for `t` equals recompute on `[0..t]`.
- **[v0.5] Extended indicators** — ATR, stochastic, z-score, momentum, volume profiles. Done when: each has a unit test vs reference.
- **[v1.0] Factor/alpha DSL** — declarative `alpha = zscore(roc(close,20))`. Done when: a DSL expression compiles to the equivalent Python pipeline.

## C. Engine Core
- **[v0.1] Timestamp-ordered event loop** — walks bars in `t` order; strategy sees only `≤ t`. *Enforcement #2.* Done when: a strategy reading `t+1` raises `LookAheadError`.
- **[v0.1] Next-bar-close fill model** — default fill at next bar close; `fill_lag` configurable. Done when: a signal on bar `t` fills at bar `t+1` close.
- **[v0.1] Portfolio simulator** — cash/position, signed qty, realized/unrealized P&L. Done when: a known trade sequence reproduces a hand-computed equity curve.
- **[v0.1] Order types** — market-at-next-close; target-weight rebalance helper. Done when: rebalance reaches target weights within tolerance.
- **[v0.1] LookAheadError hard-abort** — future read raises + kills run. Done when: harness test asserts run aborts and emits no partial result.
- **[v0.5] Limit/stop orders** — fills vs intrabar H/L with rules. Done when: a limit order fills only when price crosses it.
- **[v0.5] Fractional / multi-asset weighting** — portfolio target-weight across universe. Done when: N-asset portfolio rebalances correctly.
- **[v1.0] Walk-forward / rolling windows** — OOS scheduling harness. Done when: a walk-forward plan produces train/test partitions by date.
- **[v1.0] Vectorized sweep backend** — fast backend for large sweeps; event engine verifies. Done when: sweep results match event-engine results within tolerance.

## D. Cost & Risk Models
- **[v0.1] Flat-per-trade commission** — simplest pluggable cost. Done when: commission deducted exactly per fill.
- **[v0.1] Pluggable cost-model interface** — `apply(fill_price, qty) -> (commission, slippage)`. Done when: a custom model drops in with no core edits.
- **[v0.5] %-of-value commission + volume slippage.** Done when: cost matches formula on fixtures.
- **[v0.5] Spread / borrow cost models** — bid-ask, short borrow. Done when: short fills incur borrow cost.
- **[v1.0] Risk module (PIT-aware)** — exposure limits, sizing, drawdown guards. Done when: a breach blocks the offending order.
- **[v2.0] Barra-style risk model** — factor exposures. Done when: factor attribution produced for a portfolio.

## E. Analytics & Tearsheet
- **[v0.1] Core metrics** — CAGR, Sharpe, Sortino, Calmar, Max Drawdown. Done when: each matches a reference on a fixture equity curve.
- **[v0.1] Trade & exposure stats** — turnover, occupancy, win rate, avg hold. Done when: stats match hand calc.
- **[v0.1] Cost attribution** — return lost to commission/slippage. Done when: net = gross − attributed cost.
- **[v0.5] HTML tearsheet** — browser-renderable, shareable. Done when: opening the file shows equity+drawdown+metrics+trades.
- **[v1.0] Benchmark comparison** — vs index; alpha/beta/tracking error. Done when: beta matches OLS reference.
- **[v1.0] Multi-strategy aggregation** — portfolio-of-strategies view. Done when: combined equity = weighted sum.

## F. Overfitting / Trust Audit (the wedge)
- **[v0.1] Deflated Sharpe Ratio** — Sharpe adjusted for trials. Done when: DSR increases with fewer trials, matches paper formula.
- **[v0.1] Mandatory audit on every result** — `audit(result)` always attached; not skippable via config. Done when: removing the call fails a test; config flag can't disable it.
- **[v0.5] Backtest-overfitting (PBO) score** — PBO from trial structure. Done when: more trials → higher PBO.
- **[v0.5] Audit verdict badge** — pass/warn surfaced. Done when: badge renders from verdict.
- **[v0.5] 3 leak-failing example strategies** — reference strategies that abort if edited to peek forward. Done when: original passes; forward-peek edit raises `LookAheadError`.
- **[v1.0] CI audit gate** — PRs can't merge if audit warns. Done when: a warn-triggering PR is blocked in CI.
- **[v2.0] Public trust score** — shareable certification. Done when: a run yields a verifiable trust token.

## G. Developer Surface
- **[v0.1] Pydantic config schema** — typed, validated `Config`. Done when: invalid config raises with field-level errors.
- **[v0.1] `StrategyProtocol`** — only surface a user writes (`on_bar(ctx) -> orders`). Done when: a conforming class runs end-to-end.
- **[v0.1] CLI: `bt run --config`** — one command end-to-end. Done when: `bt run -c cfg.yaml` prints tearsheet + audit.
- **[v0.5] `pip install backtester`.** Done when: fresh env `pip install` + `bt --help` works.
- **[v0.5] Strategy templates / cookiecutter.** Done when: `bt new mystrat` scaffolds a runnable strategy.
- **[v1.0] Python SDK + docs site.** Done when: public reference builds.

## H. Database & Storage
- **[v0.1] Local analytical cache** — Parquet of adjusted bars under `~/.backtester/cache`. Done when: reload from cache reproduces in-memory bars.
- **[v0.1] Run manifest persistence** — `config_hash + data_hash + engine_version + seed`. Done when: manifest reconstructs the exact run.
- **[v0.5] DuckDB analytical store** — query layer over Parquet (bars/equity/trades). Done when: SQL returns correct range aggregates.
- **[v0.5] SQLite metadata store** — strategies/configs/runs/audits. Done when: a run row round-trips.
- **[v1.0] Postgres metadata** — multi-user ready. Done when: migrates from SQLite without data loss.
- **[v1.0] Plugin data interface** — community adapters persist via contract. Done when: adapter writes a dataset row + partitions.
- **[v2.0] Cloud columnar + hosted PG.** Done when: same queries run against cloud store.

## I. Backend Service / API
- **[v0.5] FastAPI run lifecycle** — `POST /runs`, `GET /runs/{id}`, result serving. Done when: submitting a config returns a run_id and later the result+audit.
- **[v0.5] `GET /tearsheet/{run_id}`** — structured + HTML. Done when: endpoint returns both forms.
- **[v1.0] Auth (`POST /auth/*`)** — login/register. Done when: protected routes reject unauthenticated calls.
- **[v1.0] Job workers** — queue + workers for long sweeps. Done when: a sweep runs off the request thread and reports progress.
- **[v1.0] Data pipeline API** — `POST /datasets/ingest`. Done when: ingest populates stores + provenance.
- **[v2.0] Hosted compute** — scaled workers. Done when: N parallel runs complete reliably.

## J. Frontend / Web App
- **[v0.5] Dashboard** — recent runs, trust scores, quick stats. Done when: loads run list from API.
- **[v0.5] Strategy Editor** — write/edit strategy, validate. Done when: save creates a strategy via API.
- **[v0.5] Run Launcher** — pick strategy + universe + range → launch. Done when: launch creates a run and polls status.
- **[v0.5] Tearsheet Viewer** — equity, drawdown, metrics, trades. Done when: renders a run's result.
- **[v0.5] Audit / Trust view** — DSR, PBO, badge. Done when: badge reflects verdict.
- **[v1.0] Data Manager** — ingest/inspect datasets + PIT provenance. Done when: user ingests a dataset through UI.
- **[v1.0] Account / Settings** — auth, profile. Done when: login persists session.
- **[v2.0] Billing + Marketplace + shareable trust certs.** Done when: subscribe flow + cert share work.

## K. Infrastructure & Ops
- **[v0.1] Single-process local compute** — deterministic, no network mid-run. Done when: offline run succeeds.
- **[v0.5] Sweep orchestration** — parallel local sweeps. Done when: a grid runs N configs concurrently.
- **[v1.0] CI (pytest unit + leak tests).** Done when: push runs suite + audit gate.
- **[v1.0] Pluggable object-store interface.** Done when: store swaps local↔cloud behind iface.
- **[v2.0] Hosted compute + observability dashboards.** Done when: runs visible in hosted dashboard.

## L. Open-Source & Community
- **[v0.5] OSS repo + license.** Done when: public repo with LICENSE + CONTRIBUTING.
- **[v1.0] Plugin data interface + upstream shims.** Done when: community PR adds an adapter.
- **[v2.0] Adapter marketplace.** Done when: third-party plugins installable.

## M. Business / Sustainability (v2.0)
- **[v2.0] Paid PIT data tier** — the monetizable asset. Done when: subscribe → data unlocks.
- **[v2.0] Hosted compute tier** — paid heavy runs. Done when: billing gates compute.
- **[v2.0] Open-core split** — engine free; data + compute paid. Done when: free tier runs unlimited local backtests.

---

### Feature counts
v0.1: **27** · v0.5: **20** · v1.0: **17** · v2.0: **10**. v0.1 is intentionally small and self-contained: a stranger can run one backtest end-to-end from the CLI.

# Backtesting Platform — Backend & Infrastructure Architecture

> **Status:** v0.1 design (personal research tool). Open-source roadmap target.
> **Companion doc:** `backtester-research-spike.html` (market/landscape research).
> **Read this first if:** you are about to write or review backend code. Everything here is the contract.

---

## 0. Purpose & How to Read This Doc

This document is the **single source of truth for the backend + infrastructure**. It exists so development is mechanical, not creative: every module, its boundary, its inputs/outputs, and the guarantees it must uphold are specified here.

- **Backend** = the Python library that turns *config + data* into *results*. Pure, deterministic, no UI.
- **Infrastructure** = data storage, compute, CI, and packaging that the backend runs on.

Non-negotiable design decisions are boxed in **PRINCIPLE** notes. Derivations/alternatives live in the HTML, not here.

---

## 1. Design Principles (non-negotiable)

> **PRINCIPLE 1 — No-look-ahead by default, architecturally enforced.**
> The engine makes it *structurally impossible* for a strategy to read future data. Strategies receive only state up to and including the current bar. If a strategy can leak, the run is rejected — not warned.

> **PRINCIPLE 2 — Pure runs.**
> `config (pydantic) + data → results`. No hidden globals, no network calls mid-run, no mutable singletons. Same inputs ⇒ byte-identical outputs.

> **PRINCIPLE 3 — Hybrid engine.**
> Vectorized indicator/signal computation (fast, numpy/pandas/polars) feeding a bar-by-bar portfolio simulator (correct fills, no cross-bar contamination).

> **PRINCIPLE 4 — Everything pluggable, nothing hardcoded.**
> Data source, cost model, fill model, risk model, and reporting are interfaces with swappable implementations. The core never imports a concrete vendor.

> **PRINCIPLE 5 — Trust is a feature.**
> Every result ships with an automated overfitting audit (Deflated Sharpe + backtest-overfitting score). A result without an audit is incomplete.

**Scope lock:** stocks only. Options/futures deferred (need pricing engine + vol surface + greeks).

---

## 2. System Context

```
                         ┌─────────────────────────────┐
                         │         USER / DEV          │
                         │  writes: config + strategy  │
                         └───────────────┬─────────────┘
                                         │  (pydantic Config, Strategy class)
                                         ▼
        ┌────────────────────────────────────────────────────────┐
        │                   BACKEND  (pure library)                │
        │                                                          │
        │   Data Layer ──► Indicators/Signals ──► Engine Core ──►  │
        │       │                  │                  │           │
        │   PIT loader      vectorized          bar-by-bar        │
        │   adapters        pure fns           portfolio sim      │
        │                                          │              │
        │   Cost/Risk models ◄──── fill model ◄───┘              │
        │                                          │              │
        │   Analytics ──► Tearsheet ◀── Overfitting Audit         │
        └───────────────────────────┬────────────────────────────┘
                                     │  (BacktestResult)
                                     ▼
                         ┌───────────────────────┐
                         │   INFRASTRUCTURE       │
                         │  storage · compute     │
                         │  CI audit gate · pkg   │
                         └───────────────────────┘
```

---

## 3. Backend Architecture (module breakdown)

Package root: `backtester/`. Each module owns one responsibility and imports only its own deps + the contracts in `core`.

| Module | Responsibility | Key exports | Must NOT |
|--------|---------------|-------------|----------|
| `backtester/core/` | Shared contracts & invariants | `Config`, `Bar`, `Trade`, `BacktestResult`, `StrategyProtocol` | import any vendor, do I/O |
| `backtester/data/` | Point-in-time data access | `PITDataLoader` (iface), `CSVLocalAdapter`, `YahooAdapter`, `Universe` | return future bars, mutate inputs |
| `backtester/indicators/` | Vectorized indicators & signals | pure `sma()`, `rsi()`, `cross()`, `make_signal()` | read beyond provided window |
| `backtester/engine/` | Event loop + portfolio sim | `run(config, data, strategy)`, `FillModel`, `Portfolio` | leak data, use globals |
| `backtester/costs/` | Plug-in cost & risk models | `Commission`, `Slippage`, `BaseCostModel` | — |
| `backtester/analytics/` | Metrics + tearsheet | `tearsheet(result)`, `trade_stats()`, `cost_attribution()` | — |
| `backtester/audit/` | Overfitting audit | `audit(result)` → `AuditReport` | be skippable |
| `backtester/cli.py` | `bt run --config ...` entry | CLI | business logic |

### 3.1 `core/` — the contracts everything depends on

```python
# Pseudocode — the actual contract. Names final; fields illustrative.
@dataclass(frozen=True)
class Bar:
    ts: datetime          # bar timestamp (tz-aware, UTC)
    open: float; high: float; low: float; close: float
    volume: float
    symbol: str

@dataclass(frozen=True)
class Trade:
    ts: datetime; symbol: str
    qty: float;           # signed
    fill_price: float; commission: float; slippage: float

@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.Series          # index = bar ts, no future leakage
    trades: list[Trade]
    config_hash: str                 # determinism manifest
    data_hash: str
    audit: AuditReport               # PRINCIPLE 5: always present

# Strategy contract — the ONLY surface a user writes.
class StrategyProtocol(Protocol):
    def on_bar(self, ctx: BarContext) -> list[Order]:
        ...
    # ctx exposes: current bar, indicators precomputed for [0..t],
    # portfolio state at t. It MUST NOT expose bars > t.
```

### 3.2 `data/` — point-in-time by construction

> **PRINCIPLE — Data is point-in-time or it is rejected.**
> The loader serves bars indexed by timestamp. The engine iterates in timestamp order. A strategy can only request `bar[≤ t]`. Requesting `> t` raises `LookAheadError` and aborts the run.

- `PITDataLoader` interface: `iter_bars(universe, start, end) -> Iterator[Bar]` strictly ascending in `ts`.
- Adapters implement the interface. `YahooAdapter` is **not** PIT-safe (survivorship + revisions) → flagged `research_only`. Production path uses PIT adapters (v1.0+).
- Adjustment (splits/dividends) applied at load time via an `AdjustmentPolicy`, never inside the engine.

### 3.3 `indicators/` — vectorized, windowed, pure

- All functions take a slice and return a same-length series; signal at `t` uses only `[0..t]`.
- The engine precomputes per-symbol indicator series once (vectorized), then hands the strategy the prefix up to `t` — never the full future series.

### 3.4 `engine/` — the enforcement point

```python
def run(config, data, strategy) -> BacktestResult:
    portfolio = Portfolio(config.starting_cash)
    for t, bar in enumerate(data.ascending_bars):        # PRINCIPLE 1: t-ordered
        ctx = BarContext(bar, indicators_prefix[: t + 1], portfolio.state(t))
        orders = strategy.on_bar(ctx)                    # strategy sees ≤ t only
        for o in orders:
            fill = config.fill_model.price(bar, o)        # default: next-bar close
            portfolio.apply(fill, config.cost_model)      # PRINCIPLE 4: pluggable
    result = BacktestResult(equity_curve=..., trades=..., ...)
    result.audit = audit(result)                          # PRINCIPLE 5
    return result
```

- `FillModel.default` = **next-bar close** (configurable `fill_lag`). Trades never fill on the signal bar.
- `Portfolio` is the only mutable state, owned by `run()` — no globals (Principle 2).

### 3.5 `costs/` — pluggable

`BaseCostModel.apply(fill_price, qty) -> (commission, slippage)`. Ships: `FlatPerTrade`, `PctOfValue`, `VolumeSlippage`. Easy to add (e.g., spread, borrow).

### 3.6 `analytics/` — the tearsheet

Standard metrics (all survivorship/leakage-safe by construction):
`CAGR, Sharpe, Sortino, Calmar, MaxDrawdown, Turnover, Exposure/Occupancy` + trade stats + cost attribution. Output: structured `dict` + `print()`-friendly report. (Rich HTML tearsheet deferred to v0.5.)

### 3.7 `audit/` — mandatory overfitting check

`audit(result) -> AuditReport` computing **Deflated Sharpe Ratio** and a **backtest-overfitting (PBO) score**; surfaces `prob_overfit` and a pass/warn verdict. Runs on every result; cannot be disabled via config (only by explicit env flag for internal tests).

---

## 4. The No-Look-Ahead Guarantee (how it is enforced)

This is the product wedge. It is enforced in **three independent places**, so no single bug defeats it:

1. **Data layer** — `iter_bars` yields strictly ascending timestamps; adapter cannot reorder.
2. **Engine loop** — strategy `on_bar(ctx)` receives `indicators_prefix[: t+1]` and portfolio state at `t`. `BarContext` has no method to fetch future bars; any attempt raises `LookAheadError`.
3. **Audit** — even if leakage slipped through, the overfitting audit flags anomalous Sharpe vs. PBO and warns.

> **PRINCIPLE — The engine refuses leaking strategies.** `LookAheadError` is a hard abort, not a warning. v0.5 ships 3 example strategies that *fail loudly* if edited to peek forward, proving the guarantee.

---

## 5. Infrastructure Layer

| Concern | v0.1 (now) | v0.5 | v1.0 | v2.0 |
|---------|-----------|------|------|------|
| **Storage** | local Parquet/Feather cache | same + versioned datasets | pluggable object store iface | hosted object store |
| **Data source** | CSV / Yahoo (research_only) | + 1 PIT-capable adapter | plugin adapter registry | paid PIT data marketplace |
| **Compute** | single-process, local | sweep orchestration (local parallel) | CI audit gate | hosted compute (open-core paid) |
| **Packaging** | editable install | `pip install backtester` | plugin data interface | open-core: engine free |
| **CI/CD** | pytest (unit+leak) | + audit gate on PRs | audit gate enforced | hosted runners |
| **Observability** | run manifest (config+data hash, seed) | + structured logs | + result provenance | + hosted dashboards |

**Determinism manifest (every run):** `config_hash`, `data_hash`, `engine_version`, `seed`. Re-running with identical manifest ⇒ identical `equity_curve`. This is what makes results reproducible and auditable.

**Storage layout (v0.1):**
```
~/.backtester/
  cache/<adapter>/<symbol>/<freq>.parquet   # adjusted, ascending bars
  runs/<run_id>/{config.json, result.json}  # manifest + outputs
```

---

## 6. Run Lifecycle (pure run)

```
User ──► Config (pydantic) + Strategy
        │
        ▼
  1. Validate config (pydantic)  ──fail──► error (no run)
  2. Load data via PITDataLoader  ──fail──► error
  3. Precompute indicators (vectorized, per symbol)
  4. Engine loop (t-ordered, fill at next-bar close, apply costs)
  5. Build BacktestResult
  6. Audit(result)  ──always──► attach AuditReport
  7. Persist run manifest + outputs
        │
        ▼
  BacktestResult { equity_curve, trades, audit, manifests }
```

Determinism: steps 3–6 are pure functions of (config, data, strategy). No I/O, no clock, no randomness unless `seed` is set.

---

## 7. Build Order (phases)

**v0.1 — personal tool (this build):**
`core` contracts → `data` CSV adapter + PIT iterator → `indicators` (SMA/RSI/cross) → `engine` loop + next-bar-close fill + `FlatPerTrade` cost → `analytics` tearsheet → `audit` Deflated Sharpe → `cli`. **Exit: a stranger runs one strategy end-to-end from the CLI.**

**v0.5 — launch-worthy wedge:** `pip install`; 3 leak-failing example strategies; overfitting audit surfaced in output; HTML tearsheet. *Launch trigger: stranger runs a trustworthy backtest in 5 min.*

**v1.0 — community:** plugin data interface (adapter registry), CI audit gate enforced, contribute broker/adapter shims upstream.

**v2.0 — sustainability:** paid PIT data + hosted compute (engine stays free/open-core).

---

## 8. Open Decisions (needed before v0.1 code freeze)

| # | Decision | Options | Default if undecided |
|---|----------|---------|----------------------|
| D1 | Bar granularity | daily / intraday (1m, 5m) | **daily** (simplest, no partial-close complexity) |
| D2 | First data source | CSV / Yahoo (research) / PIT vendor | **CSV local** (PIT-correct, no vendor dependency) |
| D3 | First strategy | SMA crossover / momentum / mean-reversion | **SMA crossover** (proves signal→fill→cost→report) |
| D4 | Universe size & years | e.g. 30 names / 10 yrs | **S&P-ish 30 / 5 yrs** (fast iteration) |
| D5 | DataFrame lib | pandas / polars | **pandas** (ecosystem, v0.1); polars later if slow |

These are **config parameters**, not architecture changes — the design absorbs any choice. Confirm D1–D5 to freeze the v0.1 spike; everything else is already specified.

---

## 9. Glossary

- **PIT (point-in-time):** data value as it was known *at* a given timestamp, free of later revisions/survivorship.
- **Fill model:** rule deciding execution price (default next-bar close).
- **Look-ahead bias:** using information unavailable at decision time. Three forms: direct, data-revision, knowledge.
- **Survivorship bias:** testing only on today's winners; inflates returns ~1–2%/yr.
- **Deflated Sharpe:** Sharpe adjusted for the number of trials attempted (overfitting guard).
- **PBO:** Probability of Backtest Overfitting.
- **Pure run:** `config + data → results`, deterministic, no side effects.

---

*Next doc to write after v0.1 spike: `backtester-api.md` (the public Python API + CLI reference) and `backtester-data-contracts.md` (exact field specs / adjust policies).*

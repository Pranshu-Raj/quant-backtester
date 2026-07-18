# API Reference

> **Scope:** v0.1 public Python API + CLI (build-now). The v0.5+ HTTP API is summarized at the end (full spec lives with the backend service). All signatures are the contract; names are final, field sets illustrative.
>
> **Guarantee:** every public entry point returns a deterministic result for fixed `config + data + seed`. No global state.

---

## 1. Public Python API (v0.1)

### 1.1 Configuration (`backtester.core`)
```python
from backtester.core import Config, Universe

config = Config(
    universe=Universe(symbols=["AAPL","MSFT"], start="2019-01-01", end="2024-01-01"),
    starting_cash=100_000.0,
    fill_model="next_close",        # default; fill_lag configurable
    fill_lag=1,                     # bars between signal and fill
    cost_model="flat_per_trade",    # references costs.BaseCostModel impl
    cost_params={"commission": 1.0},
    data_path="data/prices.csv",    # path the CLI uses to build the loader
    adjustment="back",              # "back" | "forward" | "" (-> AdjustmentPolicy)
    seed=42,                        # None => no randomness
    audit=True,                     # cannot be set False to skip
)
```
- **Done when:** invalid `Config` raises `pydantic.ValidationError` with field paths.

### 1.2 Data (`backtester.data`)
```python
from backtester.data import PITDataLoader, CSVLocalAdapter, AdjustmentPolicy

loader = PITDataLoader(
    adapter=CSVLocalAdapter(path="data/prices.csv"),
    adjustment=AdjustmentPolicy(mode="back"),   # back | forward
)
bars = loader.iter_bars(config.universe)        # Iterator[Bar], strictly ascending ts
```
- **Contract:** `iter_bars` yields ascending `ts` only; adapters cannot reorder.

### 1.3 Strategy (`backtester.core`)
```python
from backtester.core import StrategyProtocol, BarContext, Order

class SMACrossover:
    def __init__(self, fast=50, slow=200):
        self.fast, self.slow = fast, slow
        self._target = 0.0

    def on_bar(self, ctx: BarContext) -> list[Order]:
        # ctx exposes ONLY state <= current bar:
        #   ctx.bar, ctx.indicators (dict[str, IndicatorWindow] capped at t),
        #   ctx.portfolio (state at t). NO method to read bars > t.
        # Reading ctx.indicators["x"][t + 1] raises LookAheadError and aborts.
        fast = ctx.indicators.get("sma_fast")
        slow = ctx.indicators.get("sma_slow")
        if fast is None or slow is None or fast.t < self.slow:
            return []
        # .current() returns the indicator value at the current bar t.
        desired = 100.0 if fast.current() > slow.current() else 0.0
        if desired == self._target:
            return []
        delta = desired - self._target
        self._target = desired
        return [Order(symbol=ctx.bar.symbol, qty=delta)]
```
- **Contract:** `on_bar` returns `list[Order]`; any access beyond `t` raises `LookAheadError` and aborts the run.

### 1.4 Run (`backtester.engine`)
```python
from backtester.engine import run

result: BacktestResult = run(config, loader, SMACrossover())
# result.equity_curve : pd.Series (index = bar ts, no future leakage)
# result.trades       : list[Trade]
# result.config_hash  : str
# result.data_hash    : str
# result.audit        : AuditReport  (always present)
```

### 1.5 Analytics (`backtester.analytics`)
```python
from backtester.analytics import tearsheet, trade_stats, cost_attribution

report = tearsheet(result)         # dict: CAGR, Sharpe, Sortino, Calmar, MaxDD, ...
ts = trade_stats(result)           # turnover, occupancy, win rate, avg hold
ca = cost_attribution(result)      # commission/slippage impact
```

### 1.6 Audit (`backtester.audit`)
```python
from backtester.audit import audit, AuditReport

report: AuditReport = result.audit
report.deflated_sharpe   # float
report.pbo               # float (v0.5+)
report.verdict           # "pass" | "warn"
# audit() is invoked inside run(); cannot be disabled via Config.
```

---

## 2. CLI (v0.1)
```
# Console script (ensure the install Scripts dir is on PATH), or use the module:
python -m backtester.cli cfg.yaml                 # run; CONFIG is a positional arg
python -m backtester.cli cfg.yaml --out run1       # also persist manifest to ~/.backtester/runs/run1/
python -m backtester.cli cfg.yaml --strategy backtester.examples.sma_crossover
```
- **Config file** (`cfg.yaml`) maps 1:1 to the `Config` pydantic model. The CLI builds the PIT loader from `config.data_path` + `config.adjustment` and imports the strategy module named by `--strategy` (defaults to the bundled SMA example).
- **Output:** metrics table + audit verdict to stdout; run manifest (config_hash, data_hash, engine_version, audit) + results written under `~/.backtester/`.

---

## 3. HTTP API (v0.5+, summary — full spec with backend service)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/runs` | submit config + strategy → `run_id` |
| GET | `/runs/{id}` | poll status / fetch `BacktestResult` + `AuditReport` |
| GET | `/tearsheet/{run_id}` | structured + HTML report |
| GET | `/strategies` · POST `/strategies` | manage strategies |
| POST | `/datasets/ingest` | trigger data pipeline (v1.0) |
| POST | `/auth/*` | login/register (v1.0) |

- **Auth:** none in v0.1–v0.5 (single-user); bearer token from v1.0.
- **Run semantics:** server loads PIT bars from the analytical store, calls the *same* pure `run()`, persists `equity_curves`/`trades`/`audits`, and serves them. The no-look-ahead guarantee is unchanged — the API only passes the requested historical window; the core enforces the rest.

---

## 4. Determinism Contract
For identical `(config_hash, data_hash, engine_version, seed)` the `equity_curve` and `trades` are **byte-identical** across machines and time. Breakage of this contract is a release-blocking bug.

## 5. Known limitations (v0.1)
- **Fill lag & visible position:** orders fill `fill_lag` bars after the signal; a strategy's `ctx.portfolio` reflects fills executed *before* the current bar, so the visible position lags the decision by `fill_lag`. Reference strategies track their own intended target (not the lagged filled position) to avoid over-trading.
- **Multi-symbol fills:** `run()` currently fills a pending order at the *globally-indexed* next bar (correct for single-symbol runs). In a multi-symbol run this uses the next bar overall rather than the same symbol's next bar — fix scheduled before multi-asset support.
- **Audit PBO:** `AuditReport.pbo` defaults to `0.0` in v0.1; the backtest-overfitting score lands in v0.5.

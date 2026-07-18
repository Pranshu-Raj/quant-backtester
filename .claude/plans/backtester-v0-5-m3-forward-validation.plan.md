# Plan: Backtester v0.5 — Milestone 3 "Forward validation"

**Source PRD**: `.claude/prds/backtester-v0-5-launch-wedge.prd.md`
**Selected Milestone**: #3 Forward validation — a run validates in-sample → out-of-sample and reports the gap, so the user gets a forward check, not just in-sample fit
**Depends on**: M1 Installable (complete), M2 Trust visible (complete)
**Complexity**: Small–Medium (orchestration over existing `run`, plus one new dataclass + a text printer + a CLI command; no new deps, no engine changes)

## Summary

M3 adds a **forward-validation mode** surfaced as `bt validate`. It is a *reporting* check only — the PRD is explicit that v0.5 reports the in-sample vs out-of-sample gap and the user acts on it manually (no optimizer, no parameter re-selection). The same strategy code runs on two contiguous, non-overlapping slices of the data:

1. **In-sample** (`universe.start` → `split_date`) — the period the strategy is "tuned" on (conceptually; we do not re-fit, we just measure it).
2. **Out-of-sample** (`split_date + 1 day` → `universe.end`) — the held-out next portion.

The result surfaces the IS vs OOS gap for the headline metrics (CAGR, Sharpe, Sortino, Max Drawdown, Deflated Sharpe, audit verdict) and a `robust` / `degraded` / `failed` forward verdict. This is the core trust differentiator of the product: "does it hold up on data it never saw?"

**Two correctness decisions baked into the design:**
- **Fresh strategy instance per leg.** Strategies are stateful (`SMACrossover._target`). Reusing one instance would carry in-sample memory into OOS — a forward leak. `run_forward` calls a `make_strategy()` factory twice.
- **OOS runs at `trials=1`.** The overfitting audit measures selection overfit from *searching* configs. The OOS leg is one confirmatory run, so it is honest at `trials=1`; only the IS leg keeps the configured `trials`. This keeps the audit meaning intact across the two legs.
- **No date overlap.** IS is inclusive `[start, split_date]`; OOS is `[split_date + 1 day, end]`. The split bar belongs to IS only.

**Build note — split is computed from actual bars, not the declared date range.**
The bundled sample's `config.yaml` declares `end: 2024-12-31`, but the shipped
`prices.csv` only covered 2023 (~260 bars). A date-based split on the declared range
parked the entire OOS leg in empty 2024 → "no bars". `split_universe` therefore
discovers the real timeline by loading the bars for the configured universe and
splitting by bar count (the split bar stays in IS; OOS starts the next day). The
sample was also extended to 2021–2024 (~1040 AAA trading days) so `SMA(200)` can
trigger in both legs, and `config.yaml` `start` was moved to `2021-01-01`.

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| Engine run | `backtester/engine/engine.py:43` | `run(config, loader, strategy) -> BacktestResult` — the single primitive we orchestrate |
| Sub-config build | pydantic v2 `Config`/`Universe` | `config.model_copy(update={"universe": ...})` (no mutation, immutable-friendly) |
| No-look-ahead | `engine.run` + `LookAheadError` | a leaky strategy still aborts `run_forward` with `LookAheadError` (no partial result) |
| Metrics | `backtester/analytics/metrics.py` | `cagr`, `sharpe`, `sortino`, `max_drawdown`, `calmar` reused on each leg's equity curve |
| Audit | `backtester/audit/audit.py:51` | `audit(equity_curve, trials=...)` already called inside `run`; we read `result.audit` |
| Tearsheet print | `backtester/analytics/tearsheet.py:33` | `print_tearsheet(result) -> str` text style; `print_forward` mirrors it |
| CLI command | `backtester/cli.py:83` (`demo`) | new `validate` command with `Optional[Path]` config (defaults to bundled sample) |
| CLI strategy load | `backtester/cli.py:32` (`_load_strategy`) | add `_load_strategy_factory` to get a fresh-instance factory per run |

## Files Changed
| File | Action | Why |
|---|---|---|
| `backtester/forward.py` | CREATE | `run_forward(config, loader, make_strategy, split=0.6) -> ForwardResult`, `split_universe(loader, universe, split)`, `ForwardResult` + `ForwardGap` frozen dataclasses |
| `backtester/analytics/tearsheet.py` | UPDATE | add `print_forward(result: ForwardResult) -> str` |
| `backtester/analytics/__init__.py` | UPDATE | export `print_forward` |
| `backtester/cli.py` | UPDATE | add `validate` command + `_load_strategy_factory` helper |
| `backtester/forward/tests/test_forward.py` | CREATE | split correctness, gap reporting, fresh-instance, invalid-split + short-range guards |
| `backtester/tests/test_packaging.py` | UPDATE | add `test_validate_runs_end_to_end`, `test_validate_invalid_split_errors` |
| `backtester/examples/data/prices.csv` | UPDATE | extended to 2021–2024 (~1040 AAA trading days) so `SMA(200)` triggers in both legs |
| `backtester/examples/config.yaml` + `examples/config.yaml` | UPDATE | `start` → `2021-01-01` to use the full history |
| `README.md` | UPDATE | document `bt validate` + Forward check section |

## Tasks
1. `split_universe` + `run_forward` + dataclasses (new `backtester/forward.py`).
2. `print_forward` (tearsheet.py).
3. `validate` CLI command + `_load_strategy_factory` (cli.py).
4. Tests + docs + PRD milestone update.

## Validation
```bash
python -m backtester.cli validate                       # IS vs OOS gap report
python -m backtester.cli validate --split 0.7
python -m backtester.cli validate --strategy backtester.examples.leaky   # LookAheadError, exit 1
pytest backtester/forward/tests/test_forward.py -q
pytest backtester/tests/test_packaging.py -q
python -m ruff check backtester && pytest -q
```

## Acceptance (all met)
- [x] `bt validate` (and `bt validate --split X`) runs end-to-end on the bundled sample with no config and prints an IS vs OOS gap report.
- [x] The two legs are contiguous and non-overlapping (no shared bar); verified by `test_split_has_no_overlap`.
- [x] A fresh strategy instance is used per leg (no in-sample memory leaks forward); verified by `test_fresh_strategy_per_leg`.
- [x] OOS leg audited at `trials=1`; IS leg keeps configured `trials`.
- [x] Invalid split (`<=0` / `>=1`) and too-short ranges raise clear `ValueError`s.
- [x] `bt validate --strategy backtester.examples.leaky` still aborts with `LookAheadError` (no-look-ahead holds in forward mode).
- [x] `print_forward` shows CAGR/Sharpe/Sortino/MaxDD/DeflatedSharpe + a 3-tier forward verdict.
- [x] README documents `bt validate`; relevant tests pass; full `pytest` + `ruff` green.

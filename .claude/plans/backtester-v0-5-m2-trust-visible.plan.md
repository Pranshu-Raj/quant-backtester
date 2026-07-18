# Plan: Backtester v0.5 — Milestone 2 "Trust visible"

**Source PRD**: `.claude/prds/backtester-v0-5-launch-wedge.prd.md`
**Selected Milestone**: #2 Trust visible — every result shows the mandatory audit (Deflated Sharpe + a *real* PBO); a leak-failing example proves the engine refuses to lie
**Depends on**: M1 Installable (complete)
**Complexity**: Small–Medium (PBO math is the only non-trivial piece; the rest is surfacing + an example module)

## Summary
M1 already prints the audit verdict + Deflated Sharpe on every run (surfaced in `print_tearsheet`). M2 makes that audit *complete and credible*:
- Replace the `pbo=0.0` scaffold in `audit()` with a **computed** PBO driven by the `trials` (configurations-searched) knob, so the overfitting probability is present and non-trivial on every run.
- Ship a **leak-failing example strategy** under `backtester/examples/` that intentionally peeks past the current bar and is hard-aborted by `LookAheadError`, so a stranger can *see* the no-look-ahead enforcement instead of just reading about it.
- Surface PBO in the tearsheet audit block.

Two real sub-decisions are deferred/flagged: the PBO *formula* (analytic proxy vs empirical — see Tasks/T2 and the open question below) and whether to also compute PBO from an actual N-trial distribution (that is closer to M3/optimizer scope and is explicitly out of v0.5 per the PRD).

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| Audit output | `backtester/audit/audit.py:64` | `deflator = math.sqrt(1.0 + math.log(trials))`; DSR is a monotonic function of `trials` |
| Audit contract | `backtester/audit/report.py:27` | `AuditReport(deflated_sharpe, pbo=0.0, verdict, notes)` — `pbo` already a field |
| Enforcement | `backtester/engine/engine.py` + `test_engine.py:_LeakyStrategy` | reading `window[window.t + 1]` raises `LookAheadError` and aborts `run` |
| Example strategy | `backtester/examples/sma_crossover.py` | module exposing a `strategy` instance, runnable via `bt run --strategy` |
| Tearsheet | `backtester/analytics/tearsheet.py:53` | audit block appended after the Costs section |
| Tests | `backtester/engine/tests/test_engine.py:178` | `test_look_ahead_access_raises` proves the abort |

## Files to Change
| File | Action | Why |
|---|---|---|
| `backtester/audit/audit.py` | UPDATE | Compute `pbo` from `trials` instead of hardcoding `0.0`; thread it into `AuditReport`. |
| `backtester/audit/report.py` | (maybe) UPDATE | If the PBO proxy needs a clamp/validation, add a `field_validator` for `pbo in [0,1]`. Otherwise unchanged (field already exists). |
| `backtester/examples/leaky.py` | CREATE | Shipped strategy that peeks `t+1` and is aborted by `LookAheadError`. Proves enforcement to a stranger. |
| `backtester/analytics/tearsheet.py` | UPDATE | Add a `PBO` line to the audit block. |
| `backtester/audit/tests/test_audit.py` | UPDATE | Assert `pbo == 0` for `trials == 1` and `pbo > 0` monotonic in `trials`. |
| `backtester/tests/test_packaging.py` | UPDATE | Assert the tearsheet now contains a `PBO` line. |
| `README.md` | UPDATE | Document `bt run --strategy backtester.examples.leaky` as the "watch the engine refuse to lie" demo. |

## Tasks
### Task 1: Compute a real PBO in the audit
- **Action**: In `audit()`, derive `pbo` from `trials` (configurations searched). Recommended proxy (documented as a scaffold, v1.0 brings the empirical version):
  - `trials <= 1` → `pbo = 0.0` (no search ⇒ no selection overfitting).
  - `trials > 1` → `pbo = 1.0 - 1.0 / trials` (monotonic ↑ in `trials`, bounded in `[0,1)`, `pbo(1)=0`).
  Pass `pbo=pbo` into `AuditReport`. Keep `deflated_sharpe` math unchanged (already correct).
- **Mirror**: the existing `deflator = sqrt(1 + log(trials))` line — same `trials` knob, same monotonic intuition.
- **Validate**: `audit(curve, trials=1).pbo == 0.0`; `audit(curve, trials=10).pbo > audit(curve, trials=2).pbo > 0`.
- **Open question (user decision)**: PBO formula — see the question at the end of this plan. Option A = analytic proxy above (cheap, no engine change). Option B = empirical PBO from actually running `trials` perturbed backtests (bigger, touches the engine, risks M3/optimizer scope creep). **Default in this plan: Option A.**

### Task 2: Ship a leak-failing example strategy
- **Action**: Create `backtester/examples/leaky.py` exposing `strategy = LeakyStrategy()` where `on_bar` reads `ctx.indicators["sma_50"][ctx.indicators["sma_50"].t + 1]` (or any `t+1` peek). This triggers `LookAheadError` inside `run`, which aborts with no partial result — exactly the PRD's "leak-failing example that proves the engine refuses to lie".
- **Mirror**: `test_engine.py:_LeakyStrategy` (same peek) and `sma_crossover.py` (module-exposes-`strategy` shape).
- **Validate**: `bt run --strategy backtester.examples.leaky` exits non-zero and prints the `LookAheadError`; `test_engine.py` already asserts `_LeakyStrategy` raises. Add `test_examples_leaky_aborts` that imports the shipped module and confirms it raises via `run`.

### Task 3: Surface PBO in the tearsheet
- **Action**: In `print_tearsheet`, add `f"  PBO               : {result.audit.pbo:.4f}"` to the audit block (between verdict and notes, or after Deflated Sharpe).
- **Mirror**: existing audit block lines in `tearsheet.py:53`.
- **Validate**: `print_tearsheet(result)` contains `"PBO"`.

### Task 4: Docs + tests
- **Action**: README gets a "Trust by architecture" section pointing at `bt run --strategy backtester.examples.leaky`. `test_audit.py` gains PBO assertions; `test_packaging.py` asserts the `PBO` line is present.
- **Mirror**: `test_packaging.py` existing `test_demo_runs_end_to_end` shape.
- **Validate**: full `pytest` green; `ruff` clean.

## Validation
```bash
# PBO math
pytest backtester/audit/tests/test_audit.py -q

# Leak example aborts
python -m backtester.cli run --strategy backtester.examples.leaky   # exits non-zero, LookAheadError
pytest backtester -q                                                 # incl. test_examples_leaky_aborts

# Tearsheet shows PBO
python -m backtester.cli demo | findstr PBO

# Full gate
python -m ruff check backtester && pytest -q
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| PBO formula misread as "real empirical PBO" | Medium | Document in `audit.py` that it is a `trials`-driven proxy; empirical PBO is v1.0 |
| Empirical-PBO (Option B) creeps into an optimizer | Medium | Plan pins Option A; empirical deferred to M3/v1.0 explicitly |
| Leaky example confuses newcomers | Low | README frames it as the "engine refuses to lie" demo, not a usable strategy |

## Acceptance
- [x] `audit()` returns a computed `pbo` (not `0.0` for `trials > 1`); `pbo == 0` for `trials == 1`
- [x] `AuditReport.pbo` is bounded in `[0, 1]` on every run
- [x] `backtester/examples/leaky.py` shipped; `bt run --strategy backtester.examples.leaky` hard-aborts on look-ahead
- [x] Tearsheet audit block shows PBO alongside Deflated Sharpe + verdict
- [x] README documents the leak demo; relevant tests pass; full `pytest` + `ruff` green

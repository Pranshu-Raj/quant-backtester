# Backtester v0.5 — Launch Wedge (Trustworthy, Forward-Validated Backtests)

## Problem
Solo quants and retail strategy tinkerers cannot trust the backtests they (or others) produce: most tools test a strategy on the *same prior data* it was tuned on, so the result reflects in-sample fit rather than real-world forward performance — and the paid incumbents that exist don't stop you from cheating. Left unsolved, users keep shipping strategies that look good in backtest and fail live, and pay for tools they don't trust.

## Evidence
- **Founder-stated differentiator:** other backtesting tools test on prior (in-sample) data and don't imitate real-world conditions; this tool backtests on one portion of the data, then validates on the held-out next portion, and iterates the strategy from that forward check. This out-of-sample loop is the mechanism that makes the result trustworthy.
- **Cost/trust barrier:** the target user will not pay for incumbent tools they don't trust.
- `Assumption — needs validation via user research / prototype`: external demand for "free + architecturally trustable" specifically beating paid incumbents is not yet confirmed with outside users. The category is supported by prior landscape research; this exact wedge and its 5-minute launch trigger are not.

## Users
- **Primary:** the solo/indie quant or retail strategy tinkerer who builds and tests their own strategies and needs to trust the result before risking real capital. Starts as the author; the v0.5 bar is that a *stranger* (external tester) can do the same unaided.
- **Not for:** institutional quant desks (different compliance/data needs), crypto/FOREX/multi-asset traders (stocks-only), users who want an automated parameter optimizer to hand them a "best" strategy (out of scope for v0.5).

## Hypothesis
We believe a free, installable backtester that **enforces no-look-ahead by architecture** *and* **validates a strategy out-of-sample** (train on one data slice → check on the held-out next slice → iterate from the forward check) will give solo quants a backtest they can trust, where paid incumbents only test on prior in-sample data.
We'll know we're right when a stranger installs the tool and runs a trustworthy, forward-validated backtest in **≤ 5 minutes** without the author's help.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Time-to-first-trustworthy-backtest (new external user) | ≤ 5 minutes, from install to reading a forward-validated verdict | Timed onboarding with a stranger; self-reported + screen recording |
| Every run emits a mandatory audit | 100% of runs return Deflated Sharpe + backtest-overfitting (PBO) score | Automated check on run output |
| Enforcement is demonstrable | ≥ 1 shipped example strategy that hard-aborts on look-ahead | Example present and verified to abort |
| Forward-validation gap is reported | Every validating run reports in-sample vs out-of-sample performance | Run output contains an out-of-sample verdict |

## Scope
**MVP** — a single installable package that a stranger can run end-to-end in 5 minutes:
- One-command install + run entry point (console script).
- A run that returns a tearsheet plus the **mandatory overfitting audit** (Deflated Sharpe + PBO).
- **Leak-failing example strategies** that prove the no-look-ahead enforcement by aborting.
- A **forward-validation mode**: split the data, backtest in-sample, validate on the held-out next portion, and surface the in-sample vs out-of-sample gap.
- A minimal web interface to trigger a run and read the verdict, so non-CLI users can also hit the 5-minute bar.

**Out of scope**
- Paid point-in-time data and hosted compute — deferred to v2.0 (engine stays free).
- Multi-asset beyond stocks — stocks-only is the wedge.
- Plugin data interface — v1.0.
- CI audit gate — v1.0.
- Automated parameter optimizer that searches for the "best" strategy — v0.5 reports the forward check; acting on it stays manual.

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Installable | A new user can `pip install` and run a sample backtest unaided in < 5 min | complete | `.claude/plans/backtester-v0-5-launch-wedge.plan.md` |
| 2 | Trust visible | Every result shows the mandatory audit (Deflated Sharpe + PBO); a leak-failing example proves the engine refuses to lie | complete | `.claude/plans/backtester-v0-5-m2-trust-visible.plan.md` |
| 3 | Forward validation | A run validates in-sample → out-of-sample and reports the gap, so the user gets a forward check, not just in-sample fit | complete | `.claude/plans/backtester-v0-5-m3-forward-validation.plan.md` |
| 4 | Web UI | A minimal interface lets a non-CLI user run a backtest and read the verdict in 5 min | complete | `.claude/plans/backtester-v0-5-m4-web-ui.plan.md` |

## Open Questions
- [ ] Is "improve the strategy over time" an *automated* optimizer, or just a *reported* out-of-sample check the user acts on manually? (v0.5 assumes reported/manual.)
- [ ] What data backs the 5-minute onboarding — a bundled sample dataset, or must the user supply their own?
- [ ] Who qualifies as the "stranger" that validates the 5-minute trigger, and how is that test run?

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Forward-validation scope creeps into a full optimizer | Medium | High | Keep v0.5 to reporting the gap; optimizer explicitly out of scope |
| 5-minute trigger blocked by install/native-dependency friction | Medium | High | Bundle a sample dataset; minimize setup; test the install on a clean machine |
| Trust claim unvalidated with external users | High | Medium | Mark as assumption; validate via prototype with a stranger before v1.0 |
| Out-of-sample split misused as another fit surface | Medium | High | Audit (PBO) must reflect the forward check; document correct usage |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*

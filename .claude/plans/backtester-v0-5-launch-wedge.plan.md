# Plan: Backtester v0.5 — Milestone 1 "Installable"

**Source PRD**: `.claude/prds/backtester-v0-5-launch-wedge.prd.md`
**Selected Milestone**: #1 Installable — a new user can `pip install` and run a sample backtest unaided in < 5 min
**Complexity**: Small

## Summary
Make the package installable and runnable by a stranger with zero setup. This is mostly mechanical packaging, but it exposes one real bug: the `bt` console script depends on `typer`, which is currently a *dev-only* dependency, so a clean `pip install` would ship a broken entry point. We ship the sample dataset + config inside the package, fix runtime deps, add the missing asset packaging, reconcile the CLI with its docs, and add a smoke test that proves a bundled-sample run works.

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| Naming | `backtester/cli.py:17` | `app = typer.Typer(...)`; commands via `@app.command()` |
| Errors | `backtester/cli.py:53-55` | `typer.echo(msg, err=True)` + `raise typer.Exit(code=1)` |
| Errors | `backtester/data/loader.py:28` | domain errors subclass `ValueError` (`PITDataError`) |
| Data access | `backtester/data/adapters.py:33` | `CSVLocalAdapter(path)` + `PITDataLoader` for loading bars |
| Tests | `backtester/engine/tests/test_engine.py` | plain `test_*` functions, `tmp_path` fixture, `pytest.approx` |
| Config | `backtester/core/config.py:17` | `Config` is a pydantic model mapped 1:1 from YAML |

## Files to Change
| File | Action | Why |
|---|---|---|
| `pyproject.toml` | UPDATE | Move `typer` + `pyyaml` from `dev` extras to main `dependencies`; add `[tool.setuptools.package-data]` for `backtester/examples/**` (`.csv`, `.yaml`) so assets ship in wheel+sdist |
| `backtester/examples/data/prices.csv` | CREATE (move from `examples/data/prices.csv`) | Sample data must live inside the package to be installed |
| `backtester/examples/config.yaml` | CREATE (move from `examples/config.yaml`) | Bundled default config; `data_path` resolved via package resources, not a relative path |
| `backtester/cli.py` | UPDATE | Add a `demo` command that runs the bundled sample with no args (hits the 5-min bar); keep `run` as an explicit subcommand taking `--config`; resolve bundled paths via `importlib.resources` |
| `README.md` | UPDATE | Fix documented invocation to match real CLI (`bt demo`, `bt run --config PATH`) |
| `backtester/tests/test_packaging.py` | CREATE | Smoke test: invoke CLI on the bundled sample (Typer `CliRunner`), assert tearsheet + audit verdict; assert sample asset is locatable via `importlib.resources` |

## Tasks
### Task 1: Ship sample assets inside the package
- **Action**: Move `examples/data/prices.csv` → `backtester/examples/data/prices.csv` and `examples/config.yaml` → `backtester/examples/config.yaml`. Rewrite the bundled `config.yaml` `data_path` to be resolved at runtime from the package (not a relative filesystem path). Keep the root `examples/` for local dev convenience if desired.
- **Mirror**: `backtester/data/adapters.py:33` loading convention; no look-ahead assumptions change.
- **Validate**: `python -c "import importlib.resources as r, backtester.examples, pathlib; print(r.files('backtester.examples') / 'data' / 'prices.csv')"` resolves a real path.

### Task 2: Fix runtime dependencies + asset packaging
- **Action**: In `pyproject.toml`, move `typer` and `pyyaml` into the main `[project].dependencies` list (the `bt` script and YAML config loading need them at runtime). Add:
  ```toml
  [tool.setuptools.package-data]
  backtester = ["examples/**/*.csv", "examples/**/*.yaml"]
  ```
- **Mirror**: existing `[project].dependencies` style (already lists `pydantic`, `pandas`, `numpy`).
- **Validate**: `python -m build` produces a wheel; `unzip -l dist/*.whl` shows `backtester/examples/data/prices.csv` inside.

### Task 3: Reconcile the CLI
- **Action**: In `backtester/cli.py`, make `run` an explicit subcommand that takes `--config PATH` (positional config also accepted for backward-compat). Add `demo` command: load the bundled `config.yaml` + `prices.csv` via `importlib.resources`, run the engine, print the tearsheet. Preserve existing error handling (`typer.echo(..., err=True)` + `typer.Exit(1)`) for missing config / import failures.
- **Mirror**: `backtester/cli.py:53-55` error style; `backtester/core/config.py:17` `Config.model_validate` for YAML.
- **Validate**: `python -m backtester.cli demo` prints a tearsheet + audit verdict; `python -m backtester.cli run --config <path>` still works.

### Task 4: Fix README + add smoke test
- **Action**: Update `README.md` usage to `bt demo` and `bt run --config PATH`. Create `backtester/tests/test_packaging.py` using `typer.testing.CliRunner` to invoke `demo` and assert (a) non-zero exit, (b) tearsheet text present, (c) audit verdict in `{pass, warn}`. Mirror the plain-function + `tmp_path` style of `backtester/engine/tests/test_engine.py`.
- **Mirror**: `backtester/engine/tests/test_engine.py` test shape; `backtester/core/tests/test_contracts.py` assertions.
- **Validate**: `pytest backtester/tests/test_packaging.py` passes.

### Task 5: End-to-end install verification
- **Action**: Build the wheel, install into a clean virtual environment, and run `bt demo` (or `python -m backtester.cli demo`) to confirm the stranger flow works with no local files.
- **Mirror**: n/a (integration check).
- **Validate**: clean-venv `bt demo` outputs a tearsheet + audit within the 5-minute bar; full `pytest` still green.

## Validation
```bash
# Build + inspect wheel contains sample data
python -m build
unzip -l dist/*.whl | grep -E "examples/.*\.(csv|yaml)"

# Unit/packaging smoke
pytest backtester/tests/test_packaging.py -q

# Full suite still green
pytest -q

# Clean-install stranger flow
python -m venv /tmp/bt-venv && /tmp/bt-venv/Scripts/python -m pip install dist/*.whl
/tmp/bt-venv/Scripts/bt demo
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| `typer`/`pyyaml` missing at runtime after install | High (currently dev-only) | Task 2 moves them to main `dependencies` |
| Sample CSV not included in wheel | High (no `package_data`) | Task 2 adds `package-data`; verified via `unzip -l` |
| CLI `run` subcommand quirk consumes args | Medium | Task 3 makes `run` explicit + adds `demo`; verified via CliRunner |
| Relative `data_path` breaks post-install | High | Task 1 resolves bundled paths via `importlib.resources` |
| Root `examples/` drift from packaged copy | Low | Keep root copy for dev; `demo` uses packaged asset |

## Acceptance
- [x] `typer` + `pyyaml` are runtime dependencies
- [x] Wheel includes `backtester/examples/data/prices.csv` and `config.yaml`
- [x] `bt demo` runs a bundled sample end-to-end (tearsheet + audit) from any cwd
- [x] `bt run --config PATH` works as documented
- [x] `backtester/tests/test_packaging.py` passes; full `pytest` green
- [x] Clean-venv install + `bt demo` succeeds (stranger flow)

# Plan: Backtester v0.5 — M4 follow-up "CSV upload temp-file cleanup"

**Source PRD**: `.claude/prds/backtester-v0-5-launch-wedge.prd.md` (Milestone #4 Web UI)
**Depends on**: M4 Web UI (complete) + M4 host-lock (complete)
**Complexity**: Trivial (own the temp-file lifecycle at the request boundary + a test)

## Problem

When a user uploads a CSV via `bt web`, `_resolve_config` writes it to a
`tempfile.NamedTemporaryFile(delete=False, ..., prefix="bt-web-")` and never
removes it. The file must survive past `_resolve_config` (the engine reads it
later, inside `run`/`run_forward`), so `delete=True` can't be used directly —
hence it currently leaks one temp file per upload. This cleans that up.

## Decision

`do_POST` already owns the request lifecycle, so it owns the temp file too.
`_resolve_config` returns the temp path alongside the `Config` (or `None` when
no CSV was uploaded). `do_POST` deletes the temp file in a `finally` block, so
it is removed whether the run succeeds, the strategy is leaky, or the CSV is
bad. The CSV branch in `_resolve_config` also self-cleans if `_config_from_csv`
raises (so a malformed upload doesn't leak either).

## What it does

```python
config, tmp_csv = _resolve_config(fields, files)
try:
    ... run / validate ...
except LookAheadError:
    ...
except Exception as exc:
    ...
finally:
    if tmp_csv:
        _remove_tmp(tmp_csv)   # best-effort os.remove, ignores OSError
```

`_resolve_config` now returns `(Config, Optional[str])`; the CSV branch returns
the temp path and rolls it back internally if `_config_from_csv` fails.

## Patterns to mirror

| Category | Source | Pattern |
|---|---|---|
| Best-effort cleanup | stdlib `os.remove` in `try/except OSError` | never let cleanup crash the caller |
| Lifecycle ownership | `backtester/web.py:do_POST` | the request handler owns request-scoped resources |
| Return-tuple for out-param | small, explicit `(value, side_path)` | avoids a mutable holder; one call site |

## Files to change

| File | Action | Why |
|---|---|---|
| `backtester/web.py` | UPDATE | `import os`; add `_remove_tmp(path)`; `_resolve_config` returns `(config, tmp_path_or_None)` and self-cleans on bad CSV; `do_POST` unpacks the tuple and removes `tmp_csv` in `finally` |
| `backtester/tests/test_web.py` | UPDATE | add `test_resolve_config_csv_returns_temp_path` (contract) and `test_csv_upload_leaves_no_temp_file` (integration: no new `bt-web-*.csv` leaked after POST) |

## Tasks

1. **`web.py` — helper + resolve change.**
   - Add `import os` (module top, alongside `import html, re, tempfile`).
   - Add:
     ```python
     def _remove_tmp(path: str) -> None:
         try:
             os.remove(path)
         except OSError:
             pass
     ```
   - Change the CSV branch of `_resolve_config`:
     ```python
     csv_bytes = files.get("csv_file")
     if csv_bytes:
         tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", prefix="bt-web-")
         try:
             tmp.write(csv_bytes)
         finally:
             tmp.close()
         try:
             cfg = _config_from_csv(tmp.name)
         except Exception:
             _remove_tmp(tmp.name)
             raise
         return cfg, tmp.name
     ```
   - Change the other two returns (`config_path` branch, `_bundled_config()` branch)
     to also return a second element `None`:
     ```python
     return Config.model_validate(raw), None
     ...
     return _bundled_config(), None
     ```
2. **`web.py` — `do_POST` lifecycle.** Unpack `config, tmp_csv = _resolve_config(fields, files)`
   and wrap the whole body (run/validate + the `except` blocks) in `try/.../finally`
   so `if tmp_csv: _remove_tmp(tmp_csv)` runs on every exit path.
3. **Tests.**
   - `test_resolve_config_csv_returns_temp_path`: import `_resolve_config`; call with
     `{"mode": "run"}, {"csv_file": _CSV.encode()}`; assert it returns a 2-tuple,
     `isinstance(result[0], Config)`, `result[1]` is a truthy path string, and
     `os.path.exists(result[1])` is `True` (file must still exist right after resolve,
     because the loader reads it later).
   - `test_csv_upload_leaves_no_temp_file`: count `glob.glob(os.path.join(tempfile.gettempdir(), "bt-web-*.csv"))`
     before the POST; POST the CSV upload via the server fixture; count after; assert
     `after == before` (no new leaked temp file). This is robust to any pre-existing
     leaked files from earlier runs.

## Validation

```bash
python -m pytest backtester/tests/test_web.py -q          # new cleanup tests pass
python -m ruff check backtester && pytest -q              # full suite green, ruff clean
# manual: monitor temp dir while uploading a CSV via the UI — no bt-web-*.csv lingers
```

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Temp file removed before the engine reads it | None | cleanup happens in `finally` *after* `run`/`run_forward` return; engine reads synchronously inside them |
| `os.remove` races with an in-flight read | Very low | single-threaded per request; read completes before `run` returns |
| Flaky glob count if OS temp dir is shared | Very low | assert `after == before` (no *new* leak), tolerant of pre-existing files |

## Acceptance

- [ ] Uploaded CSV temp files are removed after the request (success, leaky, and bad-CSV paths).
- [ ] `_resolve_config` still returns a valid `Config` for CSV / config-path / bundled inputs.
- [ ] New tests cover the return contract and the no-leak behavior.
- [ ] `ruff` clean; full `pytest` green.

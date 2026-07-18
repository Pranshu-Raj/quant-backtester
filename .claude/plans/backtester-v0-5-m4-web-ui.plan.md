# Plan: Backtester v0.5 — Milestone 4 "Web UI"

**Source PRD**: `.claude/prds/backtester-v0-5-launch-wedge.prd.md`
**Selected Milestone**: #4 Web UI — a minimal interface lets a non-CLI user run a backtest and read the verdict in 5 min
**Depends on**: M1 Installable, M2 Trust visible, M3 Forward validation (all complete)
**Complexity**: Medium (a small stdlib web server + form parsing + strategy/CSV resolution; no new deps)

## Decision (from user)
- **Framework:** Zero-dependency **stdlib `http.server`** (`ThreadingHTTPServer`). No new dependencies — `bt web` works immediately after `pip install`. (Note: `ARCHITECTURE.md` targets FastAPI + React SPA for later phases; M4 is explicitly *minimal*, so we ship the lean version and stay on the path the PRD's 5-min bar requires.)
- **Scope:** Richer than the PRD's bare minimum — the form supports **inline strategy code (paste/edit)** *and* **CSV upload**, in addition to the default bundled-sample path. This is a deliberate user choice beyond "minimal trigger + verdict."

## What it does
`bt web` starts a local server at `http://127.0.0.1:8000` (binds to localhost only). A single page offers:
- **Mode:** Run (backtest + audit) or Validate (forward check).
- **Strategy:** either a module-path field (default `backtester.examples.sma_crossover`) *or* a **code textarea** that defines `strategy` / `make_strategy`.
- **Data:** optional config-path field *or* a **CSV file upload**; if neither, the **bundled sample** is used (zero setup → 5-min bar).
- **Split:** number field for Validate (default 0.6).
- Submit → renders the **tearsheet / forward report** inline (or a clear "look-ahead detected, run aborted" panel for a leaky strategy).

The core engine's no-look-ahead guarantee is untouched — the web layer is pure orchestration that calls the existing `run` / `run_forward` and reuses `print_tearsheet` / `print_forward`.

## Security boundary (must be explicit)
- Binds to **`127.0.0.1` only** (never `0.0.0.0`); no auth (single-user per `ARCHITECTURE.md` E5 until v1.0).
- **Inline strategy code is `exec`'d** and **uploaded CSV is written to a temp file then read**. This is arbitrary local code/file execution — acceptable *only* because the server is localhost, single-user, and trusted. This is documented in the README and the module docstring as a known limitation; no sandboxing is attempted (YAGNI for a local dev tool, and a real sandbox is a v1.0+ concern). All exec/parse errors are caught and shown as messages — the server never crashes.
- CSV upload is parsed by a **small hand-rolled multipart parser** (no `cgi` — removed in 3.13; no new dep).

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| Engine run | `backtester/engine/engine.py:43` | `run(config, loader, strategy)` — reused directly |
| Forward run | `backtester/forward.py` | `run_forward(config, loader, make_strategy, split)` — reused directly |
| Tearsheet print | `backtester/analytics/tearsheet.py` | `print_tearsheet` / `print_forward` text reused and wrapped in HTML |
| Strategy/loader helpers | `backtester/cli.py` | reuse `_load_strategy_factory`, `_resolve_bundled`, `_bundled_config` |
| Data adapter | `backtester/data/adapters.py` | `CSVLocalAdapter` + `PITDataLoader` + `AdjustmentPolicy` reused |
| Stdlib server | Python `http.server` | `ThreadingHTTPServer` + `BaseHTTPRequestHandler` |

## Files to Change
| File | Action | Why |
|---|---|---|
| `backtester/web.py` | CREATE | `run_web(host, port)`, `BacktesterHandler` (GET form / POST run), multipart parser, strategy-from-code + config-from-CSV resolution, HTML templates |
| `backtester/cli.py` | UPDATE | add `bt web` command (`--host` default 127.0.0.1, `--port` default 8000) |
| `backtester/web/tests/__init__.py` + `test_web.py` | CREATE | GET form, POST run/validate on bundled, leaky abort, inline code, CSV upload |
| `README.md` | UPDATE | document `bt web` + the localhost/single-user trust note |
| `.claude/plans/backtester-v0-5-m4-web-ui.plan.md` | CREATE (on build) | persisted plan per project convention |
| `.claude/prds/backtester-v0-5-launch-wedge.prd.md` | UPDATE (on build) | milestone #4 → `complete` |

## Tasks

### Task 1: `backtester/web.py` — server + handlers
- `run_web(host="127.0.0.1", port=8000)`: `ThreadingHTTPServer((host, port), BacktesterHandler).serve_forever()`.
- `BacktesterHandler(BaseHTTPRequestHandler)`:
  - `do_GET`: serve `_render_page(form=None, result=None, error=None)`.
  - `do_POST`: read body via `Content-Length`; `_parse_multipart` → fields + optional `csv_file`. Resolve config, strategy, loader; run; render. Catch `LookAheadError` → abort panel; catch `Exception` → error panel. Always 200 (never 500 on user error).
  - `_parse_multipart(body, content_type) -> (fields, files)`: boundary split, no `cgi`.
- Resolution helpers (reuse cli helpers where possible):
  - `_resolve_config(fields, files)`: CSV upload → temp file + `_config_from_csv(path)` (pandas-inferred `symbols`/`start`/`end` + sensible defaults); elif `config_path` → `Config.model_validate(yaml)`; else `_bundled_config()`.
  - `_resolve_strategy(fields)`: if `strategy_code` non-empty → `exec` in a clean namespace, extract `make_strategy` (preferred) or `strategy` (wrap as factory); else `_load_strategy_factory(strategy_module)`.
  - `_build_loader(config)`: `CSVLocalAdapter` + `AdjustmentPolicy` + `PITDataLoader` (mirrors cli).
- HTML: minimal but intentional single-page style (centered card, clear labels, verdict color block for pass/warn/robust/degraded/failed). Form uses `enctype="multipart/form-data"` (always, so one parse path). Result shown in a `<pre>`-styled block + verdict banner.

### Task 2: `bt web` CLI command
- Add to `cli.py`: `@app.command() def web(host: str = typer.Option("127.0.0.1", "--host"), port: int = typer.Option(8000, "--port"))` that imports `run_web` and serves (printing the URL). Host default is localhost-only.

### Task 3: Tests (`backtester/web/tests/test_web.py`)
- Fixture starts `ThreadingHTTPServer(("127.0.0.1", 0), BacktesterHandler)` in a daemon thread; yields `http://127.0.0.1:{port}`; shuts down after.
- `test_get_form`: GET `/` → 200, contains "Backtester" and the mode fields.
- `test_post_run_bundled`: POST mode=run → 200, contains "Tearsheet".
- `test_post_validate_bundled`: POST mode=validate → 200, contains "Forward".
- `test_post_leaky`: POST strategy=`backtester.examples.leaky` → 200 (no crash), contains "LookAheadError"/abort text.
- `test_post_inline_code`: POST `strategy_code` defining a `strategy` → 200, contains "Tearsheet".
- `test_post_csv_upload`: POST a small multipart CSV → 200, contains "Tearsheet".

### Task 4: Docs + PRD
- README: add `bt web` usage + a clear note that it binds localhost, runs user-supplied code, and is single-user (trusted-local only).
- Persist plan to `.claude/plans/backtester-v0-5-m4-web-ui.plan.md`.
- PRD milestone #4 → `complete`.

## Validation
```bash
python -m backtester.cli web --port 8731 &        # start, then:
curl -s localhost:8731 | findstr Backtester       # GET form
# POST run (bundled) via form -> contains "Tearsheet"
# POST validate -> contains "Forward"
# POST leaky strategy -> contains "LookAheadError"
python -m ruff check backtester && pytest -q       # web tests + full suite
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| `exec` of user code (injection) | N/A by design | localhost-only, single-user; documented; errors caught, server never crashes |
| `cgi` removed in 3.13 | Certain | hand-rolled multipart parser, no `cgi` import |
| CSV upload path traversal / bad format | Low | written to `tempfile` with random name; adapter validates columns; errors shown |
| Server blocks on long run | Low | `ThreadingHTTPServer` handles concurrent requests; in-process sync is the v0.5 design |
| HTML looks like a template | Low | minimal intentional style (card + verdict color block), not a default template |

## Acceptance
- [ ] `bt web` starts a localhost server with no new dependencies; `GET /` shows the form.
- [ ] A stranger can run the bundled sample (Run + Validate) and read the verdict in < 5 min, no files needed.
- [ ] Inline strategy code and CSV upload both work.
- [ ] A leaky strategy shows the "look-ahead detected, aborted" panel (no partial result); server stays up.
- [ ] Binds to `127.0.0.1` only; user-code exec is documented as localhost/single-user only.
- [ ] `ruff` clean; `pytest` (incl. web tests) green; PRD #4 marked complete.

# Plan: Backtester v0.5 — M4 follow-up "Hard-lock the web host to loopback"

**Source PRD**: `.claude/prds/backtester-v0-5-launch-wedge.prd.md` (Milestone #4 Web UI)
**Depends on**: M4 Web UI (complete)
**Complexity**: Trivial (one guard at the socket-opening boundary + a CLI UX wrapper + a test)

## Problem

`bt web` binds to `127.0.0.1` by default, but its `--host` option currently
accepts *any* value — including `0.0.0.0` — which would expose the
localhost/single-user server (which `exec`s user code) to the network. The
trust boundary documented in the README and `web.py` module docstring ("binds
to 127.0.0.1 only") is currently advisory, not enforced. This closes that gap.

## Decision (from user)

**Keep the `--host` option, but validate it against a loopback allowlist.** The
guard lives at the real socket-opening boundary (`run_web`), so every caller is
protected — not just the CLI. Non-loopback hosts are rejected with a clear
error. This preserves legitimate flexibility (`::1`) while blocking
`0.0.0.0`/external interfaces.

## What it does

A single pure helper `_is_localhost(host) -> bool` checks the host against an
explicit allowlist `{"127.0.0.1", "::1", "localhost"}`. `run_web` calls it at
the top (before `serve_forever`) and raises `ValueError` if the host is not
loopback. The CLI `web` command wraps `run_web` in a `try/except ValueError`
and exits cleanly with code 1 and the message on stderr (no traceback).

```text
bt web                 # ok  (127.0.0.1)
bt web --host ::1      # ok
bt web --host 0.0.0.0  # ERR: bt web can only bind to a loopback address (127.0.0.1, ::1, localhost)
```

## Patterns to mirror

| Category | Source | Pattern |
|---|---|---|
| Localhost-only guard | `backtester/web.py:run_web` | validate at the socket-opening primitive, not just the CLI |
| CLI clean-exit on error | `backtester/cli.py` (`run`/`validate` config-not-found) | `typer.echo(..., err=True)` + `raise typer.Exit(code=1)` |
| Pure allowlist check | stdlib `in` set membership | no hostname resolution (avoids DNS/`/etc/hosts` ambiguity) |

## Files to change

| File | Action | Why |
|---|---|---|
| `backtester/web.py` | UPDATE | add `_LOCALHOST_HOSTS` allowlist + `_is_localhost(host)`; raise `ValueError` at top of `run_web` if not loopback |
| `backtester/cli.py` | UPDATE | wrap `run_web(...)` in `try/except ValueError` → `typer.Exit(code=1)` with message; update `--host` help text to say "loopback only" |
| `backtester/tests/test_web.py` | UPDATE | add `test_run_web_rejects_non_localhost` (asserts `run_web("0.0.0.0", 0)` raises `ValueError`); add `test_is_localhost` for allowlist true/false cases |
| `README.md` | UPDATE | note that non-loopback hosts are rejected |

## Tasks

1. **`web.py` guard.** Add module-level `_LOCALHOST_HOSTS = {"127.0.0.1", "::1", "localhost"}`
   and `_is_localhost(host: str) -> bool: return host in _LOCALHOST_HOSTS`.
   At the very top of `run_web` (before building the server), add:
   ```python
   if not _is_localhost(host):
       raise ValueError(
           "bt web can only bind to a loopback address "
           "(127.0.0.1, ::1, localhost); refusing to expose the server to a network."
       )
   ```
   Placing it before `ThreadingHTTPServer(...)` means rejection happens with no
   socket opened — so the new test can assert the raise without a dangling port.
2. **`cli.py` UX wrap.** In the `web` command, wrap the `run_web(host=host, port=port)`
   call:
   ```python
   try:
       run_web(host=host, port=port)
   except ValueError as exc:
       typer.echo(str(exc), err=True)
       raise typer.Exit(code=1)
   ```
   Update the `--host` option help to: "Bind host — loopback only (127.0.0.1, ::1, localhost)."
3. **Tests.** In `test_web.py`:
   - `test_is_localhost`: `_is_localhost("127.0.0.1")` and `_is_localhost("::1")`
     and `_is_localhost("localhost")` are `True`; `_is_localhost("0.0.0.0")`,
     `_is_localhost("")`, `_is_localhost("example.com")` are `False`.
   - `test_run_web_rejects_non_localhost`: `pytest.raises(ValueError): run_web("0.0.0.0", 0)`.
4. **Docs.** README Web UI section: add one line that non-loopback hosts are rejected.

## Validation

```bash
python -m pytest backtester/tests/test_web.py -q          # new host-lock tests pass
python -m ruff check backtester && pytest -q              # full suite green, ruff clean
python -m backtester.cli web --host 0.0.0.0               # exit 1, clear stderr message, no traceback
python -m backtester.cli web --port 8731 &                # default still serves on 127.0.0.1
curl -s localhost:8731 | findstr Backtester               # form renders
```

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `localhost` resolves via `/etc/hosts` to a non-loopback IP | Very low | allowlist also covers literal `127.0.0.1`/`::1`; `localhost` kept for ergonomics, documented |
| Power user in a container needs host-reachable port | Acceptable | they can use `::1`/`127.0.0.1`; full container exposure is out of scope for the v0.5 single-user model |

## Acceptance

- [ ] `bt web --host 0.0.0.0` (and any non-loopback) exits 1 with a clear message, no traceback, no socket opened.
- [ ] `bt web` (default) and `bt web --host ::1` / `--host localhost` still serve.
- [ ] Guard lives in `run_web` (protects all callers, not just the CLI).
- [ ] New tests cover the allowlist + the reject path.
- [ ] `ruff` clean; full `pytest` green.

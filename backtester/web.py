"""Minimal localhost web UI for the backtester (Milestone 4).

``bt web`` serves a single page built on the stdlib :mod:`http.server` only —
no new dependencies, so it works immediately after ``pip install``. The web
layer is pure orchestration: it reuses the existing ``run`` / ``run_forward``
engine primitives, the ``print_tearsheet`` / ``print_forward`` reporters, and
the loader built by the CLI, then wraps the text in a small HTML page.

Security boundary (read before using)
-------------------------------------
This server binds to ``127.0.0.1`` only and is intended for a single, trusted,
local user (ARCHITECTURE.md decision E5, until v1.0). It will ``exec``
user-supplied strategy code and read uploaded CSV files. That is arbitrary
local code/file execution and is safe *only* because the server is localhost,
single-user, and trusted. There is no sandboxing (YAGNI for a local tool; a
real sandbox is a v1.0+ concern). All exec/parse errors are caught and shown
as messages, so the server never crashes on bad input. Do not expose this to a
network or untrusted users.
"""

from __future__ import annotations

import html
import os
import re
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional, Tuple

from backtester.core import LookAheadError

_DEFAULT_STRATEGY = "backtester.examples.sma_crossover"

# Hosts we will bind to. This server runs user-supplied code and is single-user
# by design (ARCHITECTURE.md E5), so it must never be reachable from a network.
_LOCALHOST_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_localhost(host: str) -> bool:
    """True only for a loopback bind address."""
    return host in _LOCALHOST_HOSTS


def _remove_tmp(path: str) -> None:
    """Best-effort delete of a request-scoped temp file; never raises."""
    try:
        os.remove(path)
    except OSError:
        pass


def _parse_multipart(body: bytes, content_type: str) -> Tuple[Dict[str, str], Dict[str, bytes]]:
    """Split a multipart/form-data body into ``(fields, files)``.

    Hand-rolled on purpose: :mod:`cgi` was removed in Python 3.13 and we add no
    dependency for one endpoint. ``fields`` maps name -> decoded text;
    ``files`` maps name -> raw bytes (filename is ignored — bytes are written
    to a random temp file downstream).
    """
    fields: Dict[str, str] = {}
    files: Dict[str, bytes] = {}
    marker = "boundary="
    idx = content_type.lower().find(marker)
    if idx == -1:
        return fields, files
    boundary = content_type[idx + len(marker) :].strip().strip('"').encode("utf-8")
    if not boundary:
        return fields, files

    for segment in body.split(b"--" + boundary):
        if segment in (b"", b"--", b"--\r\n"):
            continue
        if segment.startswith(b"\r\n"):
            segment = segment[2:]
        if b"\r\n\r\n" not in segment:
            continue  # trailing boundary marker, no headers
        raw_headers, content = segment.split(b"\r\n\r\n", 1)
        if content.endswith(b"\r\n"):
            content = content[:-2]
        headers = {}
        for line in raw_headers.split(b"\r\n"):
            if b":" in line:
                k, v = line.split(b":", 1)
                headers[k.decode().strip().lower()] = v.decode().strip()
        disposition = headers.get("content-disposition", "")
        name = _disposition_attr(disposition, "name")
        if name is None:
            continue
        if "filename" in disposition:
            files[name] = content
        else:
            fields[name] = content.decode("utf-8", errors="replace")
    return fields, files


def _disposition_attr(disposition: str, key: str) -> Optional[str]:
    match = re.search(rf'{key}="([^"]*)"', disposition)
    return match.group(1) if match else None


def _resolve_config(fields: Dict[str, str], files: Dict[str, bytes]):
    """Build a :class:`~backtester.core.Config` from uploaded CSV, a config path, or the bundle.

    Returns ``(config, tmp_csv_path)`` where ``tmp_csv_path`` is the path of a
    request-scoped temp file (created for CSV uploads) or ``None``. The caller
    owns that file and must delete it after the run (see ``BacktesterHandler.do_POST``).
    """
    from backtester.cli import _bundled_config
    from backtester.core import Config

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

    config_path = fields.get("config_path", "").strip()
    if config_path:
        from pathlib import Path

        import yaml

        raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
        return Config.model_validate(raw), None

    return _bundled_config(), None


def _config_from_csv(path: str):
    """Infer symbols/start/end from the uploaded CSV and wrap it in a Config."""
    import pandas as pd

    from backtester.core import Config

    frame = pd.read_csv(path)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    ts_col = "date" if "date" in frame.columns else ("ts" if "ts" in frame.columns else None)
    if ts_col is None:
        raise ValueError("CSV must contain a 'date' or 'ts' column")
    dates = pd.to_datetime(frame[ts_col], utc=True, errors="raise")
    symbols = sorted(frame["symbol"].astype(str).unique().tolist())
    raw = {
        "universe": {
            "symbols": symbols,
            "start": str(dates.min().date()),
            "end": str(dates.max().date()),
        },
        "data_path": str(path),
        "adjustment": "back",
    }
    return Config.model_validate(raw)


def _resolve_strategy(fields: Dict[str, str]):
    """Return a zero-arg factory yielding fresh strategy instances.

    Prefers inline ``strategy_code`` (exec'd in a clean namespace); else loads
    the ``strategy_module`` path via the CLI helper.
    """
    from backtester.cli import _load_strategy_factory

    code = fields.get("strategy_code", "").strip()
    if code:
        namespace: dict = {}
        try:
            exec(code, namespace)  # localhost/single-user trust boundary only
        except Exception as exc:  # surface compile/runtime errors as a message
            raise ValueError(f"strategy code failed: {exc}") from exc
        maker = namespace.get("make_strategy")
        if callable(maker):
            return maker
        inst = namespace.get("strategy")
        if inst is None:
            raise ValueError("strategy code must define `strategy` or `make_strategy`")
        cls = type(inst)
        return lambda: cls()

    module = fields.get("strategy_module", "").strip() or _DEFAULT_STRATEGY
    return _load_strategy_factory(module)


def _build_loader(config):
    from backtester.data import AdjustmentPolicy, CSVLocalAdapter, PITDataLoader

    adapter = CSVLocalAdapter(path=config.data_path)
    adjustment = AdjustmentPolicy(mode=config.adjustment) if config.adjustment else None
    return PITDataLoader(adapter=adapter, adjustment=adjustment)


# --- HTML -----------------------------------------------------------------


def _render_page(
    result_text: Optional[str] = None,
    verdict: Optional[str] = None,
    error: Optional[str] = None,
    form: Optional[Dict[str, str]] = None,
) -> str:
    form = form or {}
    mode = html.escape(form.get("mode", "run"))
    split = html.escape(form.get("split", "0.6"))
    strategy_module = html.escape(form.get("strategy_module", _DEFAULT_STRATEGY))
    config_path = html.escape(form.get("config_path", ""))
    strategy_code = html.escape(form.get("strategy_code", ""))

    banner = ""
    if verdict:
        banner = (
            f'<div class="banner banner-{html.escape(verdict)}">'
            f"Verdict: {html.escape(verdict)}</div>"
        )
    elif error:
        banner = f'<div class="banner banner-error">{html.escape(error)}</div>'

    result_block = ""
    if result_text:
        result_block = f"<pre>{html.escape(result_text)}</pre>"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Backtester</title>
<style>
  :root {{
    --bg: #0f1115; --card: #171a21; --ink: #e6e9ef; --muted: #9aa3b2;
    --accent: #5b8cff; --line: #2a2f3a;
    --pass: #2fbf71; --warn: #e0a93b; --robust: #2fbf71;
    --degraded: #e0a93b; --failed: #e5484d; --error: #e5484d;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--ink);
    font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    display: flex; justify-content: center; padding: 2.5rem 1rem;
  }}
  .card {{ width: 100%; max-width: 760px; background: var(--card);
    border: 1px solid var(--line); border-radius: 14px; padding: 1.75rem;
    box-shadow: 0 10px 40px rgba(0,0,0,.35); }}
  h1 {{ margin: 0 0 .25rem; font-size: 1.5rem; letter-spacing: -.01em; }}
  .sub {{ color: var(--muted); margin: 0 0 1.5rem; font-size: .9rem; }}
  label {{ display: block; margin: .85rem 0 .3rem; color: var(--muted);
    font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; }}
  .row {{ display: flex; gap: .75rem; }}
  .row > * {{ flex: 1; }}
  input[type=text], input[type=number], select, textarea {{
    width: 100%; background: #0f1115; color: var(--ink);
    border: 1px solid var(--line); border-radius: 8px; padding: .55rem .65rem;
    font: inherit; }}
  textarea {{ resize: vertical; min-height: 110px; font-family: ui-monospace, monospace; }}
  button {{ margin-top: 1.25rem; background: var(--accent); color: #fff; border: 0;
    border-radius: 8px; padding: .7rem 1.1rem; font: inherit; font-weight: 600;
    cursor: pointer; }}
  button:hover {{ filter: brightness(1.08); }}
  .banner {{ margin: 1.25rem 0 0; padding: .7rem .9rem; border-radius: 8px;
    font-weight: 600; background: #0f1115; border: 1px solid var(--line); }}
  .banner-pass, .banner-robust {{ color: var(--pass); border-color: var(--pass); }}
  .banner-warn, .banner-degraded {{ color: var(--warn); border-color: var(--warn); }}
  .banner-failed, .banner-error {{ color: var(--failed); border-color: var(--failed); }}
  pre {{ background: #0f1115; border: 1px solid var(--line); border-radius: 8px;
    padding: 1rem; margin: 1.25rem 0 0; overflow-x: auto;
    font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; }}
  .note {{ color: var(--muted); font-size: .78rem; margin-top: 1rem; }}
</style>
</head>
<body>
  <main class="card">
    <h1>Backtester</h1>
    <p class="sub">No-look-ahead backtests, run from your browser. Localhost only.</p>
    <form method="post" enctype="multipart/form-data">
      <label for="mode">Mode</label>
      <select id="mode" name="mode">
        <option value="run"{' selected' if mode == 'run' else ''}>Run (backtest + audit)</option>
        <option value="validate"
          {' selected' if mode == 'validate' else ''}>Validate (forward check)</option>
      </select>

      <label for="strategy_module">Strategy module</label>
      <input id="strategy_module" type="text" name="strategy_module" value="{strategy_module}"
        placeholder="backtester.examples.sma_crossover">

      <label for="strategy_code">…or paste strategy code</label>
      <textarea id="strategy_code" name="strategy_code"
        placeholder="strategy = MyStrategy()">{strategy_code}</textarea>

      <div class="row">
        <div>
          <label for="config_path">Config path (optional)</label>
          <input id="config_path" type="text" name="config_path" value="{config_path}">
        </div>
        <div>
          <label for="csv_file">…or upload CSV</label>
          <input id="csv_file" type="file" name="csv_file">
        </div>
      </div>

      <label for="split">In-sample split (Validate only)</label>
      <input id="split" type="number" name="split"
        step="0.05" min="0.05" max="0.95" value="{split}">

      <button type="submit">Run</button>
    </form>
    {banner}
    {result_block}
    <p class="note">This server runs locally and single-user. Inline code is executed
    and uploads are read on your machine — do not expose it to a network.</p>
  </main>
</body>
</html>"""


def run_web(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the localhost web UI and serve until interrupted."""
    if not _is_localhost(host):
        raise ValueError(
            "bt web can only bind to a loopback address (127.0.0.1, ::1, localhost); "
            "refusing to expose the server (which runs user code) to a network."
        )
    server = ThreadingHTTPServer((host, port), BacktesterHandler)
    url = f"http://{host}:{port}"
    print(f"Backtester web UI serving at {url}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


class BacktesterHandler(BaseHTTPRequestHandler):
    """Serves the form on GET and runs a backtest on POST."""

    def _send(self, html_text: str) -> None:
        body = html_text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (stdlib entry point name)
        self._send(_render_page())

    def do_POST(self) -> None:  # noqa: N802 (stdlib entry point name)
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        content_type = self.headers.get("Content-Type", "")
        fields, files = _parse_multipart(body, content_type)

        config, tmp_csv = _resolve_config(fields, files)
        try:
            loader = _build_loader(config)
            mode = fields.get("mode", "run").strip()
            if mode == "validate":
                from backtester.analytics import print_forward
                from backtester.forward import run_forward

                split = float(fields.get("split", "0.6"))
                factory = _resolve_strategy(fields)
                result = run_forward(config, loader, factory, split=split)
                self._send(
                    _render_page(
                        result_text=print_forward(result),
                        verdict=result.gap.verdict,
                        form=fields,
                    )
                )
            else:
                from backtester.analytics import print_tearsheet
                from backtester.engine import run

                strategy = _resolve_strategy(fields)()
                result = run(config, loader, strategy)
                self._send(
                    _render_page(
                        result_text=print_tearsheet(result),
                        verdict=result.audit.verdict,
                        form=fields,
                    )
                )
        except LookAheadError:
            self._send(
                _render_page(
                    error="Look-ahead detected: the engine refuses to backtest a leaky "
                    "strategy. Run aborted (no partial result).",
                    form=fields,
                )
            )
        except Exception as exc:  # never crash the server on bad input
            self._send(_render_page(error=f"{type(exc).__name__}: {exc}", form=fields))
        finally:
            if tmp_csv:
                _remove_tmp(tmp_csv)

    def log_message(self, *args) -> None:  # silence default stderr logging
        pass

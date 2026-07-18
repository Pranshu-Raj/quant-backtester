"""Tests for the minimal localhost web UI (``backtester/web.py``)."""

from __future__ import annotations

import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from backtester.web import BacktesterHandler

_SIMPLE_STRATEGY = """
from backtester.core import BarContext, Order

class Strategy:
    def on_bar(self, ctx: BarContext):
        return [Order(symbol=ctx.bar.symbol, qty=100)]

strategy = Strategy()
"""

_CSV = """date,symbol,open,high,low,close,volume
2021-01-04,ZZZ,10,11,9,10,1000
2021-01-05,ZZZ,10,12,10,11,1000
2021-01-06,ZZZ,11,12,10,11,1000
2021-01-07,ZZZ,11,13,11,12,1000
2021-01-08,ZZZ,12,13,11,12,1000
2021-01-11,ZZZ,12,13,11,12,1000
2021-01-12,ZZZ,12,14,12,13,1000
2021-01-13,ZZZ,13,14,12,13,1000
"""


def _multipart(base: str, fields: dict, files=None) -> str:
    boundary = "----btwebtestboundary"
    parts = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(value.encode() if isinstance(value, str) else value)
        parts.append(b"\r\n")
    for name, data in (files or {}).items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{name}"; filename="up.csv"\r\n'.encode()
        )
        parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
        parts.append(data)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(
        base + "/",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()


@pytest.fixture
def server_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), BacktesterHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()


def test_get_form(server_url):
    with urllib.request.urlopen(server_url) as resp:
        page = resp.read().decode()
    assert resp.status == 200
    assert "Backtester" in page
    assert 'name="mode"' in page
    assert 'name="strategy_code"' in page


def test_post_run_bundled(server_url):
    page = _multipart(server_url, {"mode": "run"})
    assert "Tearsheet" in page
    assert "Audit" in page


def test_post_validate_bundled(server_url):
    page = _multipart(server_url, {"mode": "validate", "split": "0.6"})
    assert "Forward" in page
    assert "Out-of-sample" in page


def test_post_leaky(server_url):
    page = _multipart(server_url, {"mode": "run", "strategy_module": "backtester.examples.leaky"})
    assert "Look-ahead" in page
    assert "Tearsheet" not in page


def test_post_inline_code(server_url):
    page = _multipart(server_url, {"mode": "run", "strategy_code": _SIMPLE_STRATEGY})
    assert "Tearsheet" in page


def test_post_csv_upload(server_url):
    page = _multipart(
        server_url,
        {"mode": "run", "strategy_module": "backtester.examples.sma_crossover"},
        files={"csv_file": _CSV.encode()},
    )
    assert "Tearsheet" in page


def test_is_localhost():
    from backtester.web import _is_localhost

    for ok in ("127.0.0.1", "::1", "localhost"):
        assert _is_localhost(ok) is True
    for bad in ("0.0.0.0", "", "example.com", "192.168.1.1"):
        assert _is_localhost(bad) is False


def test_run_web_rejects_non_localhost():
    from backtester.web import run_web

    with pytest.raises(ValueError):
        run_web("0.0.0.0", 0)

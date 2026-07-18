"""Packaging smoke test: a stranger can run the bundled sample with no local files.

Mirrors the plain-function + `tmp_path` style of the engine tests. Asserts the
bundled assets are locatable via ``importlib.resources`` and that ``bt demo``
produces a tearsheet with a valid audit verdict.
"""

from __future__ import annotations

import importlib.resources as resources

from typer.testing import CliRunner

from backtester.cli import app

_EXAMPLES_PKG = "backtester.examples"
runner = CliRunner()


def test_bundled_assets_locatable() -> None:
    cfg = resources.files(_EXAMPLES_PKG).joinpath("config.yaml")
    data = resources.files(_EXAMPLES_PKG).joinpath("data").joinpath("prices.csv")
    assert cfg.is_file()
    assert data.is_file()


def test_demo_runs_end_to_end() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "Tearsheet" in result.stdout
    assert "CAGR" in result.stdout
    assert ("pass" in result.stdout) or ("warn" in result.stdout)


def test_run_requires_config() -> None:
    # Without --config, Typer errors (missing required option), not a crash.
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0

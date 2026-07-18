"""Deterministic hashing for the reproducibility manifest.

Both hashes are built over a *stable* string representation so that identical
``(config, data)`` always yields identical digests regardless of process,
platform, or run order (ARCHITECTURE.md — determinism manifest, release-blocking).
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

from .config import Config
from .models import Bar


def _stable_json(payload: object) -> str:
    """Serialize ``payload`` deterministically: sorted keys, no whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def config_hash(config: Config) -> str:
    """SHA-256 of a stable JSON rendering of the config.

    Nested models (``Universe``) are serialized via pydantic's JSON mode so the
    digest is independent of Python's dict ordering.
    """
    rendered = _stable_json(config.model_dump(mode="json"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def data_hash(bars: Iterable[Bar]) -> str:
    """SHA-256 over the bar stream, in iteration order.

    Each bar contributes a single canonical line
    ``symbol|iso_ts|open|high|low|close|volume``. The digest is therefore
    independent of object identity and stable across runs for the same data.

    Note: iterating ``bars`` consumes it. That is acceptable — computing the
    digest is the caller's intent.
    """
    hasher = hashlib.sha256()
    for bar in bars:
        ts = bar.ts.isoformat()
        line = f"{bar.symbol}|{ts}|{bar.open}|{bar.high}|{bar.low}|{bar.close}|{bar.volume}"
        hasher.update(line.encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()

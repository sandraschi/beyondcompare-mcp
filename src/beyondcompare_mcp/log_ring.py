"""In-memory ring buffer for fleet dashboard log tail (stderr-safe, no stdout)."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

_MAX = 500
_lock = threading.Lock()
_entries: deque[dict[str, Any]] = deque(maxlen=_MAX)


def append_log(entry: dict[str, Any]) -> None:
    """Append a structured log entry (timestamp added if missing)."""
    row = dict(entry)
    if "ts" not in row:
        row["ts"] = time.time()
    with _lock:
        _entries.append(row)


def get_logs(limit: int = 200) -> list[dict[str, Any]]:
    """Return the most recent ``limit`` entries (oldest first within the slice)."""
    with _lock:
        snap = list(_entries)
    if limit >= len(snap):
        return snap
    return snap[-limit:]


def clear_logs() -> int:
    """Empty the ring buffer; returns the number of entries dropped."""
    with _lock:
        n = len(_entries)
        _entries.clear()
    return n

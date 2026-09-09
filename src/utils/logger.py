"""Logging strutturato JSON (SPEC §9.1)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class RunLogger:
    """Logger per-run che accoda record JSON Lines (.jsonl)."""

    def __init__(self, run_id: str, log_dir: str | Path = "docs/logs") -> None:
        self.run_id = run_id
        self.path = Path(log_dir) / f"{run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._t0 = time.monotonic()

    def log(self, state: str, sensors: dict[str, Any], actuators: dict[str, Any]) -> dict[str, Any]:
        """Accoda un record e lo restituisce."""
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "state": state,
            "sensors": sensors,
            "actuators": actuators,
            "metrics": {
                "run_id": self.run_id,
                "elapsed_time_ms": int((time.monotonic() - self._t0) * 1000),
            },
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

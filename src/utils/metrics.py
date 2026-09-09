"""Raccolta metriche di performance (SPEC §9.2)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RunMetrics:
    """Metriche aggregate di una run."""

    run_id: str
    success: bool = False
    elapsed_time_s: float = 0.0
    deviation_samples: list[float] = field(default_factory=list)
    victims_detected: int = 0
    false_positives: int = 0

    @property
    def deviation_avg(self) -> float | None:
        """Deviazione media dalla linea (None se nessun campione)."""
        if not self.deviation_samples:
            return None
        return sum(self.deviation_samples) / len(self.deviation_samples)


def load_run_log(run_id: str, log_dir: str | Path = "docs/logs") -> list[dict]:
    """Carica i record JSONL di una run."""
    path = Path(log_dir) / f"{run_id}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

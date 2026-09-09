"""Report markdown post-run dai log (SPEC §9.3)."""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def main() -> None:
    """Genera report markdown."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--glob", default="docs/logs/*.jsonl")
    args = ap.parse_args()
    lines = ["# Report run Rescue Line", ""]
    for path in sorted(glob.glob(args.glob)):
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        lines.append(f"## {Path(path).stem} — {len(rows)} tick")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report -> {args.output}")


if __name__ == "__main__":
    main()

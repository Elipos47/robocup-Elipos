"""Estrae metriche dai log JSONL (SPEC §9.2/9.3)."""

from __future__ import annotations

import argparse
import glob
import json


def summarize(path: str) -> dict:
    """Riassume un file .jsonl in metriche chiave."""
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    states = [r.get("state") for r in rows]
    return {
        "log": path,
        "ticks": len(rows),
        "states": {s: states.count(s) for s in set(states)},
        "elapsed_ms_last": (rows[-1].get("metrics", {}).get("elapsed_time_ms") if rows else None),
    }


def main() -> None:
    """CLI: stampa riepilogo JSON per ogni log."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="")
    ap.add_argument("--glob", default="docs/logs/*.jsonl")
    args = ap.parse_args()
    report = [summarize(p) for p in sorted(glob.glob(args.glob))]
    text = json.dumps(report, indent=2)
    if args.output:
        open(args.output, "w", encoding="utf-8").write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create a collision-safe local evidence directory and immutable input manifest."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local smoke run directory")
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--kind", choices=("baseline", "experiment"), required=True)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--baseline-run-id")
    args = parser.parse_args()

    run_dir = Path(args.evidence_root) / "smoke" / args.run_id
    if run_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing smoke run: {run_dir}")
    if args.kind == "experiment" and not args.baseline_run_id:
        raise SystemExit("An experiment must declare --baseline-run-id")
    if args.kind == "baseline" and args.baseline_run_id:
        raise SystemExit("A baseline cannot declare --baseline-run-id")

    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "artifacts").mkdir()
    manifest = {
        "run_id": args.run_id,
        "kind": args.kind,
        "claim": args.claim,
        "inputs": {},
        "gates": [],
        "baseline_run_id": args.baseline_run_id,
        "verdict": "PENDING",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (run_dir / "commands.txt").write_text("", encoding="utf-8")
    (run_dir / "verdict.txt").write_text("PENDING\n", encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()

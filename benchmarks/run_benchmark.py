"""CLI for the three-plan initial real-world benchmark set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from runner import run_plan


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "benchmarks"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, help="Optional directory for detected-result JSON; inputs are never modified.")
    args = parser.parse_args()

    results = []
    for plan_id in ("plan_01", "plan_02", "plan_03"):
        result = run_plan(FIXTURES / f"{plan_id}.png", FIXTURES / f"{plan_id}.annotation.json")
        results.append(result)
        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            (args.output_dir / f"{plan_id}.detected.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps({"plans": results}, indent=2))


if __name__ == "__main__":
    main()

"""Run the frozen electrical engine against the real architectural fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .electrical_benchmark import render_electrical_overlay, run_electrical_plan


def routing_comparison(v1: dict, v2: dict, v2_1: dict) -> dict:
    """Retain both measured versions without concealing route-length regressions."""
    return {"v1": v1["routing_summary"], "v2": v2["routing_summary"], "v2_1": v2_1["routing_summary"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path, help="directory containing plan_*.png")
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark_reports/electrical"))
    args = parser.parse_args()
    reports = {}
    for image_path in sorted(args.fixtures.glob("plan_*.png")):
        v1 = run_electrical_plan(image_path, routing_version="v1")
        v2 = run_electrical_plan(image_path, routing_version="v2")
        v2_1 = run_electrical_plan(image_path, routing_version="v2.1")
        v2_1["routing_comparison"] = routing_comparison(v1, v2, v2_1)
        v2_1["overlay_paths"] = {
            "v1": render_electrical_overlay(v1, args.output_dir / f"{image_path.stem}_v1_electrical.png"),
            "v2": render_electrical_overlay(v2, args.output_dir / f"{image_path.stem}_v2_electrical.png"),
            "v2_1": render_electrical_overlay(v2_1, args.output_dir / f"{image_path.stem}_v2_1_electrical.png"),
        }
        reports[image_path.stem] = v2_1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "electrical_benchmark.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()


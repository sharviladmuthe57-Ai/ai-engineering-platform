"""Run the frozen electrical engine against the real architectural fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .electrical_benchmark import render_electrical_overlay, run_electrical_plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path, help="directory containing plan_*.png")
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark_reports/electrical"))
    args = parser.parse_args()
    reports = {}
    for image_path in sorted(args.fixtures.glob("plan_*.png")):
        report = run_electrical_plan(image_path)
        report["overlay_path"] = render_electrical_overlay(
            report, args.output_dir / f"{image_path.stem}_electrical.png")
        reports[image_path.stem] = report
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "electrical_benchmark.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()

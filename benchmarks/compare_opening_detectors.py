"""Run the immutable opening benchmark against V1 and opt-in V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runner import run_plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path, help="benchmark fixture directory")
    args = parser.parse_args()
    results = {}
    for image in sorted(args.fixtures.glob("plan_*.png")):
        annotation = image.with_suffix(".annotation.json")
        results[image.stem] = {
            detector: run_plan(image, annotation, opening_detector=detector)
            for detector in ("v1", "v2", "v3")
        }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

"""Reproducible baseline benchmark for the three supplied architectural plans."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean

from core.cv_analyzer import analyze_floor_plan

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "benchmarks"


def _confidence_distribution(candidates):
    values = [float(c["confidence"]) for c in candidates]
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "mean": round(mean(values), 3) if values else None,
        "max": max(values) if values else None,
        "bins": {
            "low_lt_0_60": sum(v < .60 for v in values),
            "medium_0_60_to_0_74": sum(.60 <= v < .75 for v in values),
            "high_ge_0_75": sum(v >= .75 for v in values),
        },
    }


def _opening_metrics(detected, accepted, rejected, uncertain):
    # Only coordinate-level accepted/rejected annotations are evaluation truth.
    # Uncertain entries are deliberately excluded rather than guessed.
    if not accepted and not rejected:
        return {
            "precision": None, "recall": None,
            "false_positives": "not_evaluable",
            "false_negatives": "not_evaluable",
            "unadjudicated_detected_count": len(detected),
            "uncertain_annotation_count": len(uncertain),
        }
    raise NotImplementedError("Coordinate-level opening matching is enabled once adjudicated annotations exist.")


def run_plan(plan_id):
    annotation = json.loads((FIXTURES / f"{plan_id}.annotation.json").read_text(encoding="utf-8"))
    image_path = FIXTURES / annotation["source_image"]
    scale = annotation["scale_input"]
    result = analyze_floor_plan(
        str(image_path),
        known_width_m=scale["width_m"],
        known_height_m=scale["height_m"],
    )
    if not result["success"]:
        raise RuntimeError(result["error"])
    data = result["data"]
    openings = annotation["opening_annotations"]
    all_candidates = data.get("opening_candidates", [])
    door_candidates = [c for c in all_candidates if c["type"] == "door"]
    window_candidates = [c for c in all_candidates if c["type"] == "window"]
    return {
        "plan_id": plan_id,
        "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "scale_input": scale,
        "room_detection": {
            "expected_count": len(annotation["expected_rooms"]),
            "detected_count": len(data["rooms"]),
            "count_delta": len(data["rooms"]) - len(annotation["expected_rooms"]),
            "detected_rooms": data["rooms"],
        },
        "door_candidates": {
            "detected_count": len(door_candidates),
            "metrics": _opening_metrics(
                door_candidates, openings["accepted"], openings["rejected"], openings["uncertain"]
            ),
            "confidence_distribution": _confidence_distribution(door_candidates),
        },
        "window_candidates": {
            "detected_count": len(window_candidates),
            "metrics": _opening_metrics(
                window_candidates, openings["accepted"], openings["rejected"], openings["uncertain"]
            ),
            "confidence_distribution": _confidence_distribution(window_candidates),
        },
        "warnings": data.get("warnings", []),
        "debug": data.get("_debug", {}),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="append", choices=["plan_01", "plan_02", "plan_03"])
    args = parser.parse_args()
    reports = [run_plan(plan) for plan in (args.plan or ["plan_01", "plan_02", "plan_03"])]
    print(json.dumps({"reports": reports}, indent=2))


if __name__ == "__main__":
    main()

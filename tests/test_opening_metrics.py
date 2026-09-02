import unittest

from benchmarks.opening_metrics import evaluate_openings, validate_opening_annotations


def opening(identifier, kind, status="confirmed"):
    return {
        "id": identifier, "type": kind, "status": status,
        "center_px": {"x": 20, "y": 10},
        "endpoints_px": [{"x": 10, "y": 10}, {"x": 30, "y": 10}],
        "width_px": 20, "wall": {"orientation": "horizontal"},
    }


class OpeningMetricsTests(unittest.TestCase):
    def test_schema_validation(self):
        self.assertEqual(validate_opening_annotations([opening("door_1", "door")]), [])

    def test_matching_is_type_sensitive_and_one_to_one(self):
        truth = [opening("door_1", "door"), opening("window_1", "window")]
        detected = [
            {"id": "d1", "type": "door", "side": "top", "position_px": {"x": 20, "y": 10}, "width_px": 20},
            {"id": "d2", "type": "door", "side": "top", "position_px": {"x": 21, "y": 10}, "width_px": 20},
            {"id": "d3", "type": "window", "side": "top", "position_px": {"x": 20, "y": 10}, "width_px": 20},
        ]
        doors = evaluate_openings(detected, truth, "door")
        windows = evaluate_openings(detected, truth, "window")
        self.assertEqual(doors["true_positives"], 1)
        self.assertEqual(len(doors["duplicate_detections"]), 1)
        self.assertEqual(windows["true_positives"], 1)

    def test_uncertain_opening_is_excluded(self):
        result = evaluate_openings([], [opening("window_uncertain", "window", "uncertain")], "window")
        self.assertFalse(result["evaluated"])

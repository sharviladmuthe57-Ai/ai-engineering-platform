import unittest

from benchmarks.runner import confidence_distribution, opening_detection_result, room_detection_result
from benchmarks.geometric import evaluate
from benchmarks.opening_metrics import evaluate_openings, validate_opening_annotations


class BenchmarkMetricsTests(unittest.TestCase):
    def test_room_result_matches_types_without_geometry_claims(self):
        result = room_detection_result(
            [{"name": "bedroom"}, {"name": "bathroom"}],
            [{"type": "bedroom"}, {"type": "bathroom"}, {"type": "kitchen"}],
        )
        self.assertEqual(result["matched_by_type"], 2)
        self.assertEqual(result["false_negative_by_type"], ["kitchen"])

    def test_opening_match_reports_false_positive_and_negative(self):
        detected = [{"type": "door", "side": "bottom", "position_px": {"x": 10, "y": 10}}]
        expected = [
            {"type": "door", "side": "bottom", "status": "expected", "position_px": {"x": 12, "y": 10}},
            {"type": "door", "side": "top", "status": "expected", "position_px": {"x": 50, "y": 50}},
        ]
        result = opening_detection_result(detected, expected, "door")
        self.assertEqual(result["true_positives"], 1)
        self.assertEqual(len(result["false_negatives"]), 1)

    def test_uncertain_openings_are_not_scored_as_ground_truth(self):
        result = opening_detection_result(
            [{"type": "window", "confidence": 0.8}],
            [{"type": "window", "status": "uncertain", "position_px": {"x": 1, "y": 1}}],
            "window",
        )
        self.assertFalse(result["evaluated"])

    def test_confidence_distribution(self):
        result = confidence_distribution([{"confidence": 0.4}, {"confidence": 0.65}, {"confidence": 0.8}, {"confidence": 0.9}])
        self.assertEqual(result, {"0.00-0.49": 1, "0.50-0.69": 1, "0.70-0.84": 1, "0.85-1.00": 1})

    def test_coordinate_opening_annotations_validate(self):
        opening = {"id": "door_1", "type": "door", "status": "confirmed",
                   "center_px": {"x": 20, "y": 10},
                   "endpoints_px": [{"x": 10, "y": 10}, {"x": 30, "y": 10}],
                   "width_px": 20, "wall": {"orientation": "horizontal"}}
        self.assertEqual(validate_opening_annotations([opening]), [])

    def test_coordinate_opening_matching_is_type_sensitive_and_one_to_one(self):
        truth = [
            {"id": "door_1", "type": "door", "status": "confirmed", "center_px": {"x": 20, "y": 10},
             "endpoints_px": [{"x": 10, "y": 10}, {"x": 30, "y": 10}], "width_px": 20, "wall": {"orientation": "horizontal"}},
            {"id": "window_1", "type": "window", "status": "confirmed", "center_px": {"x": 20, "y": 10},
             "endpoints_px": [{"x": 10, "y": 10}, {"x": 30, "y": 10}], "width_px": 20, "wall": {"orientation": "horizontal"}},
        ]
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

    def test_uncertain_coordinate_openings_are_excluded(self):
        truth = [{"id": "u", "type": "window", "status": "uncertain", "center_px": {"x": 1, "y": 1},
                  "endpoints_px": [{"x": 1, "y": 1}, {"x": 2, "y": 1}], "width_px": 1,
                  "wall": {"orientation": "horizontal"}}]
        result = evaluate_openings([], truth, "window")
        self.assertFalse(result["evaluated"])

    def test_geometric_matching_is_one_to_one(self):
        detected = [
            {"id": "d1", "geometry_px": {"polygon": [[0, 0], [10, 0], [10, 10], [0, 10]], "area": 121}},
            {"id": "d2", "geometry_px": {"polygon": [[20, 0], [30, 0], [30, 10], [20, 10]], "area": 121}},
        ]
        expected = [
            {"id": "e1", "status": "confirmed", "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {"id": "e2", "status": "confirmed", "polygon": [[20, 0], [30, 0], [30, 10], [20, 10]]},
        ]
        result = evaluate(detected, expected)
        self.assertEqual(result["matched_count"], 2)
        self.assertEqual(result["false_positives"], [])
        self.assertEqual(result["missed_rooms"], [])


if __name__ == "__main__":
    unittest.main()

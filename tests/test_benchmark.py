import unittest

from benchmarks.runner import confidence_distribution, opening_detection_result, room_detection_result


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


if __name__ == "__main__":
    unittest.main()

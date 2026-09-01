import unittest

import numpy as np

from core.openings_v2 import _cluster, _exterior_sides, extract_opening_candidates_v2


class ExteriorAwareOpeningTests(unittest.TestCase):
    def test_exterior_sides_are_geometry_derived(self):
        regions = [
            {"x": 10, "y": 20, "w": 40, "h": 30},
            {"x": 50, "y": 20, "w": 40, "h": 30},
            {"x": 10, "y": 50, "w": 40, "h": 30},
            {"x": 50, "y": 50, "w": 40, "h": 30},
        ]
        sides = _exterior_sides(regions, 100, 100)
        self.assertIn((0, "top"), sides)
        self.assertIn((0, "left"), sides)
        self.assertIn((3, "bottom"), sides)
        self.assertIn((3, "right"), sides)

    def test_clustering_merges_nearby_orientation_compatible_proposals(self):
        base = {"orientation": "horizontal", "position_px": {"x": 50, "y": 20}, "width_px": 30, "exterior_wall": False}
        result = _cluster([dict(base, proposal_id="a"), dict(base, proposal_id="b", position_px={"x": 53, "y": 20})], 200)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["support_count"], 2)

    def test_v2_candidate_contract_is_legacy_compatible(self):
        wall_mask = np.full((120, 160), 255, dtype=np.uint8)
        binary = np.zeros_like(wall_mask)
        region = {"x": 30, "y": 30, "w": 80, "h": 60}
        # An exterior horizontal wall gap with nearby parallel ink strokes.
        wall_mask[25:36, 50:90] = 0
        binary[27:29, 50:90] = 255
        binary[32:34, 50:90] = 255
        candidates, debug = extract_opening_candidates_v2(wall_mask, binary, [region], scale_x_m_per_px=.05, scale_y_m_per_px=.05, W=160, H=120)
        self.assertGreaterEqual(debug["raw_proposals"], debug["final_candidates"])
        for candidate in candidates:
            self.assertTrue({"id", "type", "room_id", "position_px", "side", "width_px", "confidence", "detection_method", "provenance", "verification_status"}.issubset(candidate))
            self.assertEqual(candidate["verification_status"], "pending")


if __name__ == "__main__":
    unittest.main()


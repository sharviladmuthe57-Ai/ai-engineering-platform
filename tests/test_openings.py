import unittest

import numpy as np

from core.openings import apply_verified_openings_to_rooms, extract_opening_candidates


class OpeningCandidateTests(unittest.TestCase):
    def setUp(self):
        self.mask = np.full((120, 160), 255, dtype=np.uint8)
        self.region = {"x": 30, "y": 30, "w": 80, "h": 60}
        self.mask[85:96, 58:82] = 0
        self.mask[25:36, 50:70] = 0

    def test_candidates_expose_the_required_contract(self):
        candidates = extract_opening_candidates(
            self.mask, [self.region], scale_x_m_per_px=0.05, scale_y_m_per_px=0.05
        )
        self.assertTrue(candidates)
        required = {
            "id", "type", "room_id", "position_px", "side", "width_px",
            "confidence", "detection_method", "provenance", "verification_status",
        }
        self.assertTrue(required.issubset(candidates[0]))
        self.assertTrue(all(c["verification_status"] == "pending" for c in candidates))
        self.assertTrue(all(0 <= c["confidence"] <= 1 for c in candidates))

    def test_pending_candidates_preserve_legacy_openings(self):
        rooms = [{
            "id": "room_1", "height": 3.0,
            "doors": [{"wall": "bottom", "position": 1.0, "width": 0.9}],
            "windows": [],
        }]
        result = apply_verified_openings_to_rooms(rooms, [{
            "id": "candidate", "type": "door", "room_id": "room_1",
            "verification_status": "pending",
        }])
        self.assertEqual(result[0]["doors"], rooms[0]["doors"])

    def test_accepted_candidate_adapts_only_its_room_and_type(self):
        rooms = [
            {"id": "room_1", "height": 3.0, "doors": [], "windows": []},
            {
                "id": "room_2", "height": 4.0,
                "doors": [{"wall": "top", "position": 1.0, "width": 1.0}],
                "windows": [],
            },
        ]
        result = apply_verified_openings_to_rooms(rooms, [{
            "id": "door_1", "type": "door", "room_id": "room_1",
            "side": "bottom", "offset_px": 30, "width_px": 20,
            "scale_x_m_per_px": 0.05, "scale_y_m_per_px": 0.05,
            "verification_status": "accepted",
        }])
        self.assertEqual(result[0]["doors"][0]["candidate_id"], "door_1")
        self.assertEqual(result[0]["doors"][0]["width"], 1.0)
        self.assertEqual(result[1]["doors"], rooms[1]["doors"])


if __name__ == "__main__":
    unittest.main()

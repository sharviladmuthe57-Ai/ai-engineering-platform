import unittest

import cv2
import numpy as np

from core.opening_symbols import _swing_arc_score, classify_symbol_aware


def proposal(side="top", width=40):
    if side in ("top", "bottom"):
        y = 50 if side == "top" else 110
        return {"side": side, "width_px": width, "position_px": {"x": 80, "y": y},
                "endpoints_px": [{"x": 60, "y": y}, {"x": 100, "y": y}]}
    x = 50 if side == "left" else 110
    return {"side": side, "width_px": width, "position_px": {"x": x, "y": 80},
            "endpoints_px": [{"x": x, "y": 60}, {"x": x, "y": 100}]}


def region():
    return {"x": 20, "y": 20, "w": 120, "h": 120}


def symbol_drawing(side="top", include_arc=True, include_leaf=True):
    image = np.zeros((160, 160), dtype=np.uint8)
    p = proposal(side)
    hinge = tuple(p["endpoints_px"][0].values())
    # Quarter arcs and leaves lie strictly in the room-facing half-plane.
    angles = {"top": (0, 90), "bottom": (180, 270),
              "left": (270, 360), "right": (90, 180)}[side]
    leaf_end = {"top": (hinge[0], hinge[1] + 38), "bottom": (hinge[0], hinge[1] - 38),
                "left": (hinge[0] + 38, hinge[1]), "right": (hinge[0] - 38, hinge[1])}[side]
    if include_arc:
        cv2.ellipse(image, hinge, (38, 38), 0, *angles, 255, 2)
    if include_leaf:
        cv2.line(image, hinge, leaf_end, 255, 2)
    return image, p


class SymbolAwareOpeningTests(unittest.TestCase):
    def classify(self, image, p, **kwargs):
        return classify_symbol_aware(
            image, np.zeros_like(image), p, region(), exterior_score=kwargs.pop("exterior_score", 0),
            parallel_window_score=kwargs.pop("parallel_window_score", 0),
            fixture_noise_penalty=kwargs.pop("fixture_noise_penalty", 0),
            v2_door_eligible=kwargs.pop("v2_door_eligible", True),
            v2_window_eligible=kwargs.pop("v2_window_eligible", False), **kwargs)

    def test_valid_door_swing_arc_near_hinge_is_scored(self):
        image, p = symbol_drawing(include_leaf=False)
        self.assertGreaterEqual(_swing_arc_score(image, p, region()), .42)

    def test_unrelated_circle_is_not_a_door_swing(self):
        image = np.zeros((160, 160), dtype=np.uint8)
        cv2.circle(image, (128, 128), 20, 255, 2)
        self.assertEqual(_swing_arc_score(image, proposal(), region()), 0.0)

    def test_door_leaf_and_combined_symbol_evidence(self):
        leaf_only, p = symbol_drawing(include_arc=False)
        result = self.classify(leaf_only, p)
        self.assertGreaterEqual(result["door_leaf_score"], .62)
        combined, p = symbol_drawing()
        self.assertEqual(self.classify(combined, p)["classification"], "door")

    def test_parallel_exterior_band_is_a_window_when_no_door_symbol_exists(self):
        image = np.zeros((160, 160), dtype=np.uint8)
        result = self.classify(image, proposal(), exterior_score=1, parallel_window_score=1,
                               v2_door_eligible=False, v2_window_eligible=True)
        self.assertEqual(result["classification"], "window")

    def test_large_exterior_door_with_leaf_is_not_automatically_a_window(self):
        image, p = symbol_drawing()
        result = self.classify(image, p, exterior_score=1, parallel_window_score=1,
                               v2_door_eligible=True, v2_window_eligible=True)
        self.assertEqual(result["classification"], "door")

    def test_fixture_noise_suppresses_unanchored_bathroom_symbols(self):
        image, p = symbol_drawing()
        result = self.classify(image, p, fixture_noise_penalty=.85)
        self.assertEqual(result["classification"], "uncertain")

    def test_conflicting_or_weak_evidence_is_uncertain(self):
        image = np.zeros((160, 160), dtype=np.uint8)
        result = self.classify(image, proposal(), exterior_score=1, parallel_window_score=.1,
                               v2_door_eligible=False, v2_window_eligible=False)
        self.assertEqual(result["classification"], "uncertain")

    def test_all_wall_orientations_support_interior_door_symbols(self):
        for side in ("top", "bottom", "left", "right"):
            with self.subTest(side=side):
                image, p = symbol_drawing(side)
                self.assertEqual(self.classify(image, p)["classification"], "door")


if __name__ == "__main__":
    unittest.main()

import unittest

import cv2
import numpy as np

from core.cv_analyzer import find_room_regions


class RoomSegmentationTests(unittest.TestCase):
    def test_filters_page_edge_dimension_band_but_keeps_small_room(self):
        """Filters page-relative artifacts without rejecting a compact WC."""
        width = height = 1000
        walls = np.full((height, width), 255, dtype=np.uint8)

        # A compact 60 x 60 enclosed room (the floor is black after inversion).
        cv2.rectangle(walls, (200, 200), (260, 260), 0, thickness=-1)
        # A narrow, page-edge dimension/artifact band.
        cv2.rectangle(walls, (10, 100), (70, 900), 0, thickness=-1)

        regions = find_room_regions(walls, width, height)
        boxes = {(region["x"], region["y"], region["w"], region["h"])
                 for region in regions}

        self.assertTrue(any(200 <= x <= 205 and 200 <= y <= 205
                            for x, y, _, _ in boxes))
        self.assertFalse(any(x < 75 and h > 700
                             for x, _, _, h in boxes))

import math
import unittest

from core.geometry import generate_layout


def room(identifier, x, y, width, height, name="bedroom", doors=None):
    return {"id": identifier, "name": name, "x": x, "y": y, "width": width, "height": height,
            "doors": doors or []}


def inside(point, candidate):
    return (candidate["x"] <= point[0] <= candidate["x"] + candidate["width"] and
            candidate["y"] <= point[1] <= candidate["y"] + candidate["height"])


class PlacementV2Tests(unittest.TestCase):
    def layout(self, rooms):
        return generate_layout({"rooms": rooms, "detected_elements": []}, placement_version="v2")

    def test_ids_are_unique_stable_and_component_counts_are_preserved(self):
        rooms = [room("living", 0, 0, 8, 6, "living")]
        legacy = generate_layout({"rooms": rooms, "detected_elements": []}, placement_version="v1")
        first = self.layout(rooms)
        second = self.layout(rooms)
        ids = [component["id"] for component in first["placed_components"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(first["placed_components"], second["placed_components"])
        self.assertEqual(len(legacy["placed_components"]), len(first["placed_components"]))

    def test_bathroom_switch_is_offset_inside_from_its_legacy_outside_door_proposal(self):
        bathroom = room("bath", 0, 0, 3, 2.5, "bathroom", [{"wall": "bottom", "position": 1.5}])
        switch = next(component for component in self.layout([bathroom])["placed_components"] if component["comp_id"] == "switch_1way")
        self.assertTrue(inside(switch["pos"], bathroom))
        self.assertEqual(switch["door_source"], "legacy_door")
        self.assertTrue(switch["placement_adjusted"])
        self.assertGreater(switch["pos"][1], bathroom["y"])

    def test_accepted_door_is_preferred_and_missing_door_uses_wall_fallback(self):
        accepted = {"wall": "right", "position": 2.0, "source": "verified_opening_candidate", "candidate_id": "accepted"}
        legacy = {"wall": "bottom", "position": 3.0}
        bedroom = room("bed", 0, 0, 6, 4, "bedroom", [legacy, accepted])
        switch = next(component for component in self.layout([bedroom])["placed_components"] if component["comp_id"] == "switch_1way")
        self.assertEqual(switch["door_source"], "accepted_opening")
        self.assertGreater(switch["pos"][0], 5.0)
        fallback = next(component for component in self.layout([room("plain", 0, 0, 6, 4)])["placed_components"] if component["comp_id"] == "switch_1way")
        self.assertEqual(fallback["door_source"], "wall_fallback")

    def test_wall_and_interior_components_stay_inside_and_separated(self):
        living = room("living", 0, 0, 8, 6, "living")
        components = self.layout([living])["placed_components"]
        non_db = [component for component in components if component["comp_id"] != "db"]
        self.assertTrue(all(inside(component["pos"], living) for component in non_db))
        self.assertTrue(all(math.dist(first["pos"], second["pos"]) > .12
                            for index, first in enumerate(non_db) for second in non_db[index + 1:]))
        ceiling = [component for component in non_db if component["comp_id"] in {"ceiling_light", "ceiling_fan"}]
        self.assertTrue(all(component["wall_side"] is None for component in ceiling))
        mounted = [component for component in non_db if component["wall_side"]]
        for component in mounted:
            x, y = component["pos"]
            side = component["wall_side"]
            distance = {
                "left": x - living["x"], "right": living["x"] + living["width"] - x,
                "bottom": y - living["y"], "top": living["y"] + living["height"] - y,
            }[side]
            self.assertLessEqual(distance, .30)

    def test_routes_remain_v2_1_compatible_after_validated_placement(self):
        rooms = [
            room("a", 0, 0, 4, 4, "bedroom", [{"wall": "right", "position": 2.0}]),
            room("b", 4, 0, 4, 4, "bedroom", [{"wall": "left", "position": 2.0}]),
        ]
        layout = self.layout(rooms)
        self.assertTrue(all(route["routing_version"] == "v2.1" for route in layout["wire_routes"]))
        self.assertTrue(all(not route["fallback_used"] for route in layout["wire_routes"]))
        destinations = {component["id"] for component in layout["placed_components"]}
        self.assertTrue(all(route["to"] in destinations for route in layout["wire_routes"]))


if __name__ == "__main__":
    unittest.main()

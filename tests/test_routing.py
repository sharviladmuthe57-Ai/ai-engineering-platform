import unittest

from core.routing import build_room_graph, route_component


def room(identifier, x, y, width, height):
    return {"id": identifier, "x": x, "y": y, "width": width, "height": height}


def inside(point, candidate):
    return (candidate["x"] <= point[0] <= candidate["x"] + candidate["width"] and
            candidate["y"] <= point[1] <= candidate["y"] + candidate["height"])


class RoutingV2Tests(unittest.TestCase):
    def test_same_room_route_is_architecture_aware_and_stays_inside(self):
        rooms = [room("a", 0, 0, 4, 4)]
        result = route_component((.5, .5), (3.5, 3.0), "a", rooms)
        self.assertTrue(result["architecture_aware"])
        self.assertFalse(result["fallback_used"])
        self.assertEqual(result["traversed_rooms"], ["a"])
        self.assertTrue(all(inside(point, rooms[0]) for point in result["waypoints"]))

    def test_adjacent_rooms_use_a_shared_boundary_transition(self):
        rooms = [room("a", 0, 0, 4, 4), room("b", 4, 0, 4, 4)]
        result = route_component((.5, .5), (7.5, 3.5), "b", rooms)
        self.assertTrue(result["architecture_aware"])
        self.assertEqual(result["traversed_rooms"], ["a", "b"])
        self.assertEqual(result["controlled_transitions"][0]["type"], "near_shared_boundary")
        self.assertEqual(result["controlled_transitions"][0]["gap_m"], 0.0)

    def test_narrow_geometric_gap_is_an_explicit_controlled_transition(self):
        rooms = [room("a", 0, 0, 4, 4), room("b", 4.15, 0, 4, 4)]
        graph = build_room_graph(rooms)
        result = route_component((.5, .5), (7.5, 3.5), "b", rooms)
        self.assertIn("a", graph)
        self.assertTrue(result["architecture_aware"])
        self.assertEqual(result["controlled_transitions"][0]["gap_m"], .15)

    def test_disconnected_rooms_report_a_deterministic_fallback(self):
        rooms = [room("a", 0, 0, 4, 4), room("b", 8, 0, 4, 4)]
        first = route_component((.5, .5), (11.5, 3.5), "b", rooms)
        second = route_component((.5, .5), (11.5, 3.5), "b", rooms)
        self.assertTrue(first["fallback_used"])
        self.assertFalse(first["architecture_aware"])
        self.assertEqual(first["fallback_reason"], "no_room_connectivity_path")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

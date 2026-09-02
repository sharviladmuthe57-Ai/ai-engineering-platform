import unittest

from core.openings import apply_verified_openings_to_rooms
from core.routing import build_room_graph, route_component


def room(identifier, x, y, width, height):
    return {"id": identifier, "x": x, "y": y, "width": width, "height": height}


def inside(point, candidate):
    return (candidate["x"] <= point[0] <= candidate["x"] + candidate["width"] and
            candidate["y"] <= point[1] <= candidate["y"] + candidate["height"])


class RoutingV2Tests(unittest.TestCase):
    def adjacent_rooms(self):
        return [room("a", 0, 0, 4, 4), room("b", 4, 0, 4, 4)]

    def test_same_room_route_is_architecture_aware_and_stays_inside(self):
        rooms = [room("a", 0, 0, 4, 4)]
        result = route_component((.5, .5), (3.5, 3.0), "a", rooms)
        self.assertTrue(result["architecture_aware"])
        self.assertFalse(result["fallback_used"])
        self.assertEqual(result["traversed_rooms"], ["a"])
        self.assertTrue(all(inside(point, rooms[0]) for point in result["waypoints"]))

    def test_adjacent_rooms_use_a_shared_boundary_transition(self):
        rooms = self.adjacent_rooms()
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

    def test_accepted_candidate_adapted_door_is_preferred_as_a_portal(self):
        rooms = self.adjacent_rooms()
        accepted = [{
            "id": "accepted_a_b", "room_id": "a", "type": "door", "verification_status": "accepted",
            "side": "right", "offset_px": 2, "width_px": 1,
            "scale_x_m_per_px": 1, "scale_y_m_per_px": 1,
        }]
        adapted = apply_verified_openings_to_rooms(rooms, accepted)
        result = route_component((.5, .5), (7.5, 3.5), "b", adapted, routing_version="v2.1")
        transition = result["controlled_transitions"][0]
        self.assertEqual(transition["portal_type"], "accepted_opening")
        self.assertEqual(transition["provenance"], "verified_opening_candidate")
        self.assertIn("accepted_a_b", transition["portal_id"])

    def test_pending_and_rejected_candidates_are_not_used_as_portals(self):
        for status in ("pending", "rejected"):
            with self.subTest(status=status):
                rooms = self.adjacent_rooms()
                candidates = [{
                    "id": f"{status}_a_b", "room_id": "a", "type": "door", "verification_status": status,
                    "side": "right", "offset_px": 2, "width_px": 1,
                    "scale_x_m_per_px": 1, "scale_y_m_per_px": 1,
                }]
                adapted = apply_verified_openings_to_rooms(rooms, candidates)
                result = route_component((.5, .5), (7.5, 3.5), "b", adapted, routing_version="v2.1")
                self.assertEqual(result["controlled_transitions"][0]["portal_type"], "geometric_fallback")

    def test_legacy_door_portal_is_used_before_geometry_fallback(self):
        rooms = self.adjacent_rooms()
        rooms[0]["doors"] = [{"wall": "right", "position": 2.0, "width": .9}]
        result = route_component((.5, .5), (7.5, 3.5), "b", rooms, routing_version="v2.1")
        self.assertEqual(result["controlled_transitions"][0]["portal_type"], "legacy_opening")

    def test_portal_selection_is_deterministic_and_prefers_accepted_over_legacy(self):
        rooms = self.adjacent_rooms()
        rooms[0]["doors"] = [
            {"wall": "right", "position": 1.0, "width": .9},
            {"wall": "right", "position": 2.0, "width": .9, "source": "verified_opening_candidate", "candidate_id": "approved"},
        ]
        first = route_component((.5, .5), (7.5, 3.5), "b", rooms, routing_version="v2.1")
        second = route_component((.5, .5), (7.5, 3.5), "b", rooms, routing_version="v2.1")
        self.assertEqual(first, second)
        self.assertEqual(first["controlled_transitions"][0]["portal_type"], "accepted_opening")


if __name__ == "__main__":
    unittest.main()

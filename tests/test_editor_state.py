import json
import unittest

from core.editor_state import (
    EditorStateError, add_component, create_project_state, delete_component,
    move_component, reset_project_state,
)
from core.geometry import generate_layout


def room(identifier, x, y, name="bedroom"):
    return {"id": identifier, "name": name, "x": x, "y": y, "width": 4.0, "height": 4.0,
            "doors": [{"wall": "right" if identifier == "a" else "left", "position": 2.0}]}


def generated_layout():
    return generate_layout({"rooms": [room("a", 0, 0), room("b", 4, 0)], "detected_elements": []})


def bom_count(state, label):
    return next(item["qty"] for item in state["bom"] if item["item"] == label)


class EditorStateTests(unittest.TestCase):
    def setUp(self):
        self.layout = generated_layout()
        self.state = create_project_state("project1", self.layout, .01)
        self.target = next(item for item in self.state["components"] if item["room_id"] == "b" and item["comp_id"] != "db")

    def test_move_preserves_id_recomputes_only_target_route_and_updates_wire(self):
        identifier = self.target["id"]
        before_route = next(route for route in self.state["routes"] if route["to"] == identifier)
        before_wire = self.state["total_wire_m"]
        move_component(self.state, identifier, [7.4, 3.2])
        moved = next(item for item in self.state["components"] if item["id"] == identifier)
        after_route = next(route for route in self.state["routes"] if route["to"] == identifier)
        self.assertEqual(moved["id"], identifier)
        self.assertEqual(moved["pos"], [7.4, 3.2])
        self.assertEqual(moved["position_source"], "user_modified")
        self.assertEqual(after_route["route_source"], "generated_after_edit")
        self.assertNotEqual(before_route["length_m"], after_route["length_m"])
        self.assertNotEqual(before_wire, self.state["total_wire_m"])
        self.assertTrue(all(not route["fallback_used"] for route in self.state["routes"]))

    def test_add_delete_and_bom_are_stable_and_json_persistable(self):
        before_components = len(self.state["components"])
        before_lights = bom_count(self.state, "Ceiling Light")
        add_component(self.state, "ceiling_light", "a", [1.2, 1.2])
        added = self.state["components"][-1]
        self.assertEqual(added["id"], "user_ceiling_light_0001")
        self.assertEqual(added["position_source"], "user_added")
        self.assertEqual(len(self.state["components"]), before_components + 1)
        self.assertEqual(bom_count(self.state, "Ceiling Light"), before_lights + 1)
        self.assertTrue(any(route["to"] == added["id"] for route in self.state["routes"]))
        persisted = json.loads(json.dumps(self.state))
        self.assertEqual(persisted["components"][-1]["id"], added["id"])
        delete_component(self.state, added["id"])
        self.assertEqual(len(self.state["components"]), before_components)
        self.assertEqual(bom_count(self.state, "Ceiling Light"), before_lights)
        self.assertFalse(any(route["to"] == added["id"] for route in self.state["routes"]))

    def test_invalid_positions_and_ids_fail_safely(self):
        with self.assertRaises(EditorStateError):
            move_component(self.state, "missing", [1, 1])
        with self.assertRaises(EditorStateError):
            move_component(self.state, self.target["id"], [99, 99])
        with self.assertRaises(EditorStateError):
            add_component(self.state, "not_a_component", "a", [1, 1])
        with self.assertRaises(EditorStateError):
            delete_component(self.state, "db_main")

    def test_reset_recovers_generated_state_after_edits(self):
        original_ids = [item["id"] for item in self.state["components"]]
        move_component(self.state, self.target["id"], [7.4, 3.2])
        add_component(self.state, "outlet_2pin", "a", [1.2, 1.2])
        reset = reset_project_state("project1", self.layout, .01, self.state["revision_number"])
        self.assertFalse(reset["edited"])
        self.assertEqual([item["id"] for item in reset["components"]], original_ids)
        self.assertTrue(all(item["position_source"] == "generated" for item in reset["components"]))
        self.assertGreater(reset["revision_number"], self.state["revision_number"])


if __name__ == "__main__":
    unittest.main()

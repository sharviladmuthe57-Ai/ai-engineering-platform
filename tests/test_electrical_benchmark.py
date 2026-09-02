import unittest

import numpy as np

from benchmarks.electrical_benchmark import (
    _bom_audit, _component_records, _quality, _route_records, _room_expectations,
)
from benchmarks.electrical_expectations import validate_expectations


def layout_fixture():
    room = {"id": "room_1", "name": "bedroom", "x": 0.0, "y": 0.0,
            "width": 5.0, "height": 4.0, "doors": [{"wall": "bottom", "position": 2.0}]}
    placed = [
        {"id": "db_main", "room_id": "entry", "room_name": "distribution", "comp_id": "db", "label": "Distribution Board", "symbol": "db", "pos": (0.3, 3.5), "qty": 1},
        {"id": "room_1_ceiling_light_0", "room_id": "room_1", "room_name": "bedroom", "comp_id": "ceiling_light", "label": "Ceiling Light", "symbol": "light", "pos": (2.5, 2.0), "qty": 1},
        {"id": "room_1_switch_1way_0", "room_id": "room_1", "room_name": "bedroom", "comp_id": "switch_1way", "label": "1-Way Switch", "symbol": "switch", "pos": (2.0, .3), "qty": 1},
        {"id": "room_1_outlet_5pin_0", "room_id": "room_1", "room_name": "bedroom", "comp_id": "outlet_5pin", "label": "5-Pin Socket (15A)", "symbol": "outlet", "pos": (4.75, 2.0), "qty": 1},
    ]
    route = {"from": "db", "to": "room_1_ceiling_light", "waypoints": [(0.3, 3.5), (2.5, 3.5), (2.5, 2.0)], "length_m": 4.37, "symbol": "light"}
    bom = [{"item": component["label"], "qty": 1, "unit": "pcs"} for component in placed]
    return {"rooms": [room], "placed_components": placed, "wire_routes": [route], "bom": bom, "total_wire_m": 4.37}


class ElectricalBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.layout = layout_fixture()
        self.mask = np.zeros((100, 100), dtype=np.uint8)
        self.records, self.collisions = _component_records(self.layout, self.mask, .05, .05)

    def test_expectation_schema_is_valid(self):
        self.assertEqual(validate_expectations(), [])

    def test_components_have_finite_coordinates_and_valid_room_context(self):
        self.assertTrue(all(record["coordinates_finite"] for record in self.records))
        self.assertEqual(len({record["id"] for record in self.records}), len(self.records))
        self.assertTrue(next(record for record in self.records if record["component_type"] == "db")["coordinates_finite"])
        room_components = [record for record in self.records if record["component_type"] != "db"]
        self.assertTrue(all(record["inside_intended_room"] for record in room_components))

    def test_wall_and_switch_to_door_metrics(self):
        switch = next(record for record in self.records if record["component_type"] == "switch_1way")
        outlet = next(record for record in self.records if record["component_type"] == "outlet_5pin")
        self.assertAlmostEqual(switch["distance_to_nearest_usable_legacy_door_m"], .3)
        self.assertEqual(outlet["associated_wall_side"], "right")
        self.assertTrue(outlet["near_associated_wall"])

    def test_routes_are_non_negative_and_deterministic(self):
        first = _route_records(self.layout, self.mask, .05, .05)
        second = _route_records(self.layout, self.mask, .05, .05)
        self.assertEqual(first, second)
        self.assertTrue(all(route["raw_length_m"] >= 0 and route["reported_length_m"] >= 0 for route in first))

    def test_boq_reconciles_direct_component_instances(self):
        audit = _bom_audit(self.layout)
        self.assertTrue(all(item["difference"] == 0 for item in audit["direct_component_reconciliation"]))

    def test_room_expectations_detect_obvious_missing_categories(self):
        expectations = _room_expectations(self.layout, self.records)
        self.assertIn("fan", expectations[0]["missing_categories"])

    def test_quality_reports_collisions_without_mutating_layout(self):
        routes = _route_records(self.layout, self.mask, .05, .05)
        quality = _quality(self.records, routes, self.collisions)
        self.assertEqual(quality["outside_building_components"], 0)
        self.assertEqual(quality["outside_building_routes"], 0)


if __name__ == "__main__":
    unittest.main()

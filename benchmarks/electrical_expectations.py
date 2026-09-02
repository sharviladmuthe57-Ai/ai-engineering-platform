"""Broad electrical-intent expectations used only by the benchmark.

These are omission-detection expectations, not electrical-code compliance
rules and never feed the production rule engine.
"""

from __future__ import annotations

from typing import Any


EXPECTATIONS: dict[str, dict[str, Any]] = {
    "bedroom": {"expected": {"lighting", "fan", "switch", "socket", "ac"}},
    "living": {"expected": {"lighting", "fan", "switch", "socket", "ac"}},
    "dining": {"expected": {"lighting", "switch", "socket"}},
    "kitchen": {"expected": {"lighting", "switch", "socket", "power", "exhaust"}},
    "bathroom": {"expected": {"lighting", "switch", "exhaust"}},
    "office": {"expected": {"lighting", "fan", "switch", "socket", "data", "ac"}},
    "study": {"expected": {"lighting", "fan", "switch", "socket", "data"}},
    "store": {"expected": {"lighting", "switch", "socket"}},
    "verandah": {"expected": {"lighting", "switch"}},
    "corridor": {"expected": {"lighting", "switch"}},
    "staircase": {"expected": {"lighting", "switch"}},
    "lobby": {"expected": {"lighting", "switch"}},
    "garage": {"expected": {"lighting", "switch", "socket"}},
    "balcony": {"expected": {"lighting", "switch"}},
    "puja_room": {"expected": {"lighting", "switch"}},
    "servant_room": {"expected": {"lighting", "fan", "switch", "socket"}},
}


COMPONENT_CATEGORIES = {
    "ceiling_light": "lighting", "emergency_light": "lighting",
    "ceiling_fan": "fan", "exhaust_fan": "exhaust",
    "switch_1way": "switch", "switch_2way": "switch",
    "outlet_5pin": "socket", "outlet_2pin": "socket",
    "ac_point": "ac", "tv_point": "data", "wifi_point": "data",
    "fridge_point": "power", "chimney_point": "power",
    "ro_point": "power", "microwave_point": "power",
    "washing_point": "power", "geyser_point": "power",
    "doorbell_point": "bell", "db": "db",
}


def validate_expectations(schema: dict[str, dict[str, Any]] = EXPECTATIONS) -> list[str]:
    valid = set(COMPONENT_CATEGORIES.values())
    errors = []
    for room_type, value in schema.items():
        expected = value.get("expected")
        if not isinstance(expected, set) or not expected:
            errors.append(f"{room_type}: expected must be a non-empty set")
        elif not expected <= valid:
            errors.append(f"{room_type}: invalid categories {sorted(expected - valid)}")
    return errors


def expectation_for(room_type: str) -> set[str]:
    return set(EXPECTATIONS.get(room_type, {}).get("expected", set()))


def category_for(component_id: str) -> str | None:
    return COMPONENT_CATEGORIES.get(component_id)

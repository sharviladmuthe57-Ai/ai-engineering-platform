import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as web_app
from core.geometry import generate_layout


def layout_fixture():
    rooms = [
        {"id": "a", "name": "bedroom", "x": 0.0, "y": 0.0, "width": 4.0, "height": 4.0,
         "doors": [{"wall": "right", "position": 2.0}]},
        {"id": "b", "name": "bedroom", "x": 4.0, "y": 0.0, "width": 4.0, "height": 4.0,
         "doors": [{"wall": "left", "position": 2.0}]},
    ]
    return generate_layout({"rooms": rooms, "detected_elements": []})


class EditorApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.jobs = Path(self.temp.name)
        self.patcher = patch.object(web_app, "JOBS", self.jobs)
        self.patcher.start()
        self.job_id = "editor01"
        job = {
            "status": "completed", "created_at": "2026-01-01T00:00:00",
            "vision_data": {"_debug": {"scale_mppx": .01}}, "layout": layout_fixture(),
        }
        (self.jobs / f"{self.job_id}.json").write_text(json.dumps(job))
        self.client = TestClient(web_app.app)

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_project_operations_persist_and_invalid_ids_are_safe(self):
        missing = self.client.get("/project/missing")
        self.assertEqual(missing.status_code, 404)
        initial = self.client.get(f"/project/{self.job_id}")
        self.assertEqual(initial.status_code, 200)
        project = initial.json()
        target = next(component for component in project["components"] if component["room_id"] == "b")
        invalid = self.client.patch(f"/project/{self.job_id}/components/missing", json={"position": [5, 1]})
        self.assertEqual(invalid.status_code, 400)
        moved = self.client.patch(f"/project/{self.job_id}/components/{target['id']}", json={"position": [7.4, 3.2]})
        self.assertEqual(moved.status_code, 200)
        self.assertEqual(next(component for component in moved.json()["components"] if component["id"] == target["id"])["position_source"], "user_modified")
        reloaded = self.client.get(f"/project/{self.job_id}").json()
        self.assertEqual(next(component for component in reloaded["components"] if component["id"] == target["id"])["pos"], [7.4, 3.2])
        added = self.client.post(f"/project/{self.job_id}/components", json={"component_type": "ceiling_light", "room_id": "a", "position": [1.2, 1.2]})
        self.assertEqual(added.status_code, 201)
        added_id = added.json()["components"][-1]["id"]
        deleted = self.client.delete(f"/project/{self.job_id}/components/{added_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(any(component["id"] == added_id for component in deleted.json()["components"]))
        saved = self.client.post(f"/project/{self.job_id}/save")
        self.assertEqual(saved.status_code, 200)
        reset = self.client.post(f"/project/{self.job_id}/reset")
        self.assertEqual(reset.status_code, 200)
        self.assertFalse(reset.json()["edited"])


if __name__ == "__main__":
    unittest.main()

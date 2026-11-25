"""Run against an isolated Compose project from within the API container."""
import base64
import json
import os
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from scripts.publish_event import publish, publisher
from tests.test_events import IMAGE, VIDEO, event

BASE = os.getenv("TEST_API_URL", "http://localhost:8000")


def request(path, authorized=True):
    headers = {"Authorization": "Bearer " + os.environ["API_TOKEN"]} if authorized else {}
    with urlopen(Request(BASE + path, headers=headers), timeout=12) as result:
        return result.read()


def wait_for(path):
    for _ in range(40):
        try:
            return request(path)
        except HTTPError as error:
            if error.code not in {404, 503}:
                raise
        except URLError:
            pass
        time.sleep(1)
    raise AssertionError(f"Timed out: {path}")


class ComposeTests(unittest.TestCase):
    def test_ingest_and_read(self):
        wait_for("/health/ready")
        with self.assertRaises(HTTPError) as denied:
            request("/api/v1/detections", authorized=False)
        self.assertEqual(denied.exception.code, 401)
        legacy = json.loads(request("/api/v1/detections/1"))
        self.assertEqual(legacy["drone_id"], "pre-migration")
        self.assertIsNone(legacy["event_id"])
        event_id = str(uuid4())
        sensor_id = str(uuid4())
        raw = event(event_id=event_id, sensor_id=sensor_id, metadata={"camera": 2},
                    image_base64=base64.b64encode(IMAGE).decode(),
                    video_base64=base64.b64encode(VIDEO).decode())
        path = "/api/v1/detections/" + event_id
        # The running subscriber needs a session before the first test publish.
        for _ in range(8):
            try:
                publish(raw)
                row = json.loads(wait_for(path))
                break
            except (AssertionError, ConnectionError):
                time.sleep(2)
        else:
            self.fail("Worker did not persist the event")
        publish(raw)
        sentinel = str(uuid4())
        publish(event(event_id=sentinel, sensor_id=sensor_id))
        wait_for("/api/v1/detections/" + sentinel)
        self.assertEqual(row["metadata"], {"camera": 2})
        self.assertEqual(request(row["image_path"]), IMAGE)
        self.assertEqual(request(row["video_path"]), VIDEO)
        page = json.loads(request(f"/api/v1/detections?sensor_id={sensor_id}&limit=1"))
        self.assertEqual(page["items"][0]["event_id"], sentinel)
        next_page = json.loads(request(
            f"/api/v1/detections?sensor_id={sensor_id}&limit=1&before_id={page['next_before_id']}"))
        self.assertEqual([item["event_id"] for item in next_page["items"]], [event_id])
        self.assertIsNone(next_page["next_before_id"])
        self.assertIn(b"drone_backend_ready 1.0", request("/metrics"))

    def test_qos_burst(self):
        wait_for("/health/ready")
        sensor_id = str(uuid4())
        ids = [str(uuid4()) for _ in range(50)]
        payloads = [event(event_id=event_id, sensor_id=sensor_id,
                          image_base64=base64.b64encode(IMAGE).decode()) for event_id in ids]
        started = time.monotonic()
        with publisher() as send:
            for payload in payloads:
                send(payload)
        wait_for("/api/v1/detections/" + ids[-1])
        page = json.loads(request(f"/api/v1/detections?sensor_id={sensor_id}&limit=100"))
        self.assertEqual([item["event_id"] for item in page["items"]], list(reversed(ids)))
        print(f"Stored 50 MQTT test events in {time.monotonic() - started:.2f}s")

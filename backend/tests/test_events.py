import base64
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from scripts.events import parse_event
from scripts.ingestion_worker import on_message

IMAGE = b"\xff\xd8\xff\xd9"
VIDEO = b"\x00\x00\x00\x08ftyp"


def event(**fields):
    return json.dumps({"drone_id": "drone-01", "confidence": 0.9, "status": "TRACKING", **fields}).encode()


class EventTests(unittest.TestCase):
    def test_legacy_identity_survives_retry(self):
        first = parse_event(event())
        second = parse_event(b'{ "status":"TRACKING", "confidence":0.9, "drone_id":"drone-01" }')
        self.assertEqual(first[1:3], second[1:3])

    def test_explicit_identity_and_media(self):
        event_id = str(uuid4())
        parsed = parse_event(event(event_id=event_id,
                                   image_base64=base64.b64encode(IMAGE).decode(),
                                   video_base64=base64.b64encode(VIDEO).decode()))
        self.assertEqual(parsed[1], event_id)
        self.assertEqual(parsed[3:], (IMAGE, VIDEO))

    def test_invalid_values(self):
        for fields in ({"confidence": -1}, {"image_base64": "?"}, {"image_base64": "YWJj"},
                       {"detected_at": "2026-11-25T10:00:00"}, {"metadata": {"key": "\x00"}}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                parse_event(event(**fields))

    @patch("scripts.ingestion_worker.persist")
    def test_ack_after_success_and_on_invalid_but_not_on_dependency_failure(self, persist):
        client = Mock()
        client.ack.return_value = 0
        state = {}
        message = SimpleNamespace(payload=event(), retain=False, qos=1, mid=17)
        on_message(client, state, message)
        client.ack.assert_called_once_with(17, 1)
        client.reset_mock()
        persist.side_effect = OSError("no storage")
        on_message(client, state, message)
        client.ack.assert_not_called()
        client.disconnect.assert_called_once()
        self.assertTrue(state["retry"])
        message.payload = b"{}"
        on_message(client, state, message)
        client.ack.assert_called_once_with(17, 1)

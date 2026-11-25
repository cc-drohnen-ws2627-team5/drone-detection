import base64
import json
import sys
from uuid import NAMESPACE_DNS, uuid5

from scripts.publish_event import publish
from tests.test_compose import wait_for
from tests.test_events import IMAGE, event

EVENT = str(uuid5(NAMESPACE_DNS, "task3-recovery-test"))
if sys.argv[1] == "publish":
    publish(event(event_id=EVENT, status="RECOVERY_TEST", image_base64=base64.b64encode(IMAGE).decode()))
else:
    detection = json.loads(wait_for("/api/v1/detections/" + EVENT))
    assert detection["status"] == "RECOVERY_TEST", detection
    print("MQTT event recovered after MinIO outage")

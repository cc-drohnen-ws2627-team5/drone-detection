import json
from datetime import datetime, timezone
from uuid import uuid4

from .publish_event import publish


if __name__ == "__main__":
    payload = {
        "event_id": str(uuid4()),
        "drone_id": "drone-alpha-01",
        "confidence": 0.94,
        "status": "INTRUSION_DETECTED",
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }
    print(publish(json.dumps(payload).encode()))

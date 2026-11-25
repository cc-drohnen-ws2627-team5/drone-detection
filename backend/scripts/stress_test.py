import argparse
import base64
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .publish_event import publisher


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path, help="JPEG snapshot to attach")
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()
    image = base64.b64encode(args.image.read_bytes()).decode()
    start = time.monotonic()
    with publisher() as send:
        for _ in range(args.count):
            payload = {
                "event_id": str(uuid4()),
                "drone_id": "drone-load-test",
                "confidence": 0.9,
                "status": "TRACKING",
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "image_base64": image,
            }
            send(json.dumps(payload).encode())
    print(f"{args.count} broker acknowledgements in {time.monotonic() - start:.2f}s")

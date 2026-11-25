import os
from pathlib import Path


def required(name):
    path = os.environ.get(f"{name}_FILE")
    value = Path(path).read_text().rstrip("\r\n") if path else os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


TOPIC = os.getenv("MQTT_TOPIC", "drone/detections")
BUCKET = os.getenv("S3_BUCKET", "drone-snapshots")
MAX_PACKET_BYTES = 16 * 1024 * 1024
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_VIDEO_BYTES = 6 * 1024 * 1024

import json
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC = "drone/detections"

def publish_mock_event():
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    else:
        client = mqtt.Client()

    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    payload = {
        "drone_id": "drone-alpha-01",
        "confidence": 0.94,
        "status": "INTRUSION_DETECTED",
        "image_url": "drone-snapshots/test_frame.jpg",
        "detected_at": datetime.now(timezone.utc).isoformat()
    }

    message = json.dumps(payload)
    info = client.publish(TOPIC, message, qos=1)
    info.wait_for_publish()

    print(f"[+] Published mock detection event to '{TOPIC}':")
    print(json.dumps(payload, indent=2))

    time.sleep(0.5)
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    publish_mock_event()

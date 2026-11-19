import json
import random
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC = "drone/detections"
TOTAL_EVENTS = 50

# Minimal valid 1x1 JPEG encoded in base64
SAMPLE_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////"
    "////////////////////////////////////////////////////////wgALCAAB"
    "AAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
)

def run_stress_test():
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    else:
        client = mqtt.Client()

    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    print(f"[*] Publishing a burst of {TOTAL_EVENTS} detection events to '{TOPIC}'...")
    start_time = time.perf_counter()

    for i in range(1, TOTAL_EVENTS + 1):
        payload = {
            "drone_id": f"drone-alpha-{(i % 5) + 1:02d}",
            "confidence": round(random.uniform(0.75, 0.99), 2),
            "status": "INTRUSION_DETECTED" if i % 2 == 0 else "TRACKING",
            "image_base64": SAMPLE_JPEG_B64,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        info = client.publish(TOPIC, json.dumps(payload), qos=1)
        info.wait_for_publish()

    elapsed = time.perf_counter() - start_time
    print(f"[✓] Published {TOTAL_EVENTS} events in {elapsed:.2f} seconds ({TOTAL_EVENTS / elapsed:.1f} msg/sec)")

    time.sleep(1.0)
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    run_stress_test()

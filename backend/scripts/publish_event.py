import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path

import paho.mqtt.client as mqtt

from .events import parse_event
from .settings import TOPIC, required


@contextmanager
def publisher():
    connected = threading.Event()
    acknowledged = threading.Event()
    connections = []
    acknowledgements = []
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
    client.username_pw_set(os.getenv("MQTT_USERNAME", "sensor"), required("MQTT_PASSWORD"))
    client.tls_set(ca_certs=required("MQTT_CA_FILE"))

    def on_connect(client, userdata, flags, reason, properties):
        connections.append(reason)
        connected.set()

    def on_publish(client, userdata, mid, reason, properties):
        acknowledgements.append((mid, reason))
        acknowledged.set()

    def send(raw):
        _, event_id, *_ = parse_event(raw)
        acknowledged.clear()
        delivery = client.publish(TOPIC, raw, qos=1)
        delivery.wait_for_publish(timeout=15)
        if not delivery.is_published() or not acknowledged.is_set():
            raise TimeoutError(f"No broker acknowledgement for {event_id}")
        mid, reason = acknowledgements.pop(0)
        if mid != delivery.mid or reason.value != 0:
            raise ConnectionError(f"Broker did not route {event_id}: {reason}")
        return event_id

    client.on_connect = on_connect
    client.on_publish = on_publish
    client.connect_async(os.getenv("MQTT_HOST", "localhost"), int(os.getenv("MQTT_PORT", "8883")))
    client.loop_start()
    try:
        if not connected.wait(10) or connections[0].is_failure:
            raise ConnectionError("MQTT connection failed")
        yield send
    finally:
        client.disconnect()
        client.loop_stop()


def publish(raw):
    with publisher() as send:
        return send(raw)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Publish a detection JSON file via authenticated MQTT.")
    parser.add_argument("event", type=Path)
    args = parser.parse_args()
    raw = args.event.read_bytes()
    fields = json.loads(raw)
    if not fields.get("event_id") or not fields.get("detected_at"):
        parser.error("save a stable event_id and detected_at in the event file before publishing")
    print(publish(raw))

import logging
import os
import sys
import time

import paho.mqtt.client as mqtt

from .events import parse_event
from .settings import TOPIC, required
from .storage import EventConflict, ensure_bucket, persist

LOG = logging.getLogger(__name__)


def on_connect(client, state, flags, reason, properties):
    if reason.is_failure:
        LOG.error("MQTT connection refused: %s", reason)
        return
    client.subscribe(TOPIC, qos=1)


def on_subscribe(client, state, mid, reasons, properties):
    if reasons and not reasons[0].is_failure:
        LOG.info("Subscribed to %s with QoS %s", TOPIC, reasons[0].value)
    else:
        LOG.error("Broker rejected subscription to %s", TOPIC)
        state["retry"] = True
        client.disconnect()


def on_message(client, state, message):
    try:
        if message.retain:
            raise ValueError("retained detections are unsupported")
        parsed = parse_event(message.payload)
    except (ValueError, RecursionError) as error:
        LOG.warning("Discarding invalid detection (%s)", type(error).__name__)
    else:
        if not store_or_retry(client, state, parsed):
            return
    if message.qos and client.ack(message.mid, message.qos) != mqtt.MQTT_ERR_SUCCESS:
        state["retry"] = True
        client.disconnect()


def store_or_retry(client, state, parsed):
    try:
        created = persist(parsed)
        LOG.info("event_id=%s created=%s", parsed[1], created)
    except EventConflict:
        LOG.warning("Conflicting payload for event_id=%s", parsed[1])
    except Exception as error:
        LOG.error("Storage unavailable (%s), leaving event unacknowledged", type(error).__name__)
        state["retry"] = True
        client.disconnect()
        return False
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    state = {"retry": False}
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=required("MQTT_CLIENT_ID"),
        clean_session=False,
        userdata=state,
        protocol=mqtt.MQTTv311,
        manual_ack=True,
    )
    client.username_pw_set(required("MQTT_USERNAME"), required("MQTT_PASSWORD"))
    client.tls_set(ca_certs=required("MQTT_CA_FILE"))
    client.reconnect_delay_set(min_delay=2, max_delay=30)
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.enable_logger()
    try:
        ensure_bucket()
    except Exception as error:
        LOG.error("Cannot initialize object storage (%s)", type(error).__name__)
        time.sleep(5)
        return 1
    client.connect_async(os.getenv("MQTT_HOST", "mqtt-broker"), int(os.getenv("MQTT_PORT", "8883")), 60)
    client.loop_forever(retry_first_connection=True)
    if state["retry"]:
        time.sleep(5)
    return 1


if __name__ == "__main__":
    sys.exit(main())

import os

import paho.mqtt.client as mqtt

from .settings import TOPIC, required


def on_connect(client, userdata, flags, reason, properties):
    if not reason.is_failure:
        client.subscribe(TOPIC, qos=1)


if __name__ == "__main__":
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(required("MQTT_USERNAME"), required("MQTT_PASSWORD"))
    client.tls_set(ca_certs=required("MQTT_CA_FILE"))
    client.on_connect = on_connect
    client.on_message = lambda client, userdata, message: print(f"{message.topic}: {len(message.payload)} bytes")
    client.connect_async(os.getenv("MQTT_HOST", "localhost"), int(os.getenv("MQTT_PORT", "8883")))
    client.loop_forever(retry_first_connection=True)

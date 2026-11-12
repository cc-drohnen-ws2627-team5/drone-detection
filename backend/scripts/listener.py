import json
import paho.mqtt.client as mqtt

BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC = "drone/detections"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[+] Connected to Mosquitto broker at {BROKER_HOST}:{BROKER_PORT}")
        client.subscribe(TOPIC)
        print(f"[*] Subscribed to topic: '{TOPIC}'")
    else:
        print(f"[-] Connection failed with return code: {rc}")

def on_message(client, userdata, msg):
    raw_payload = msg.payload.decode("utf-8")
    try:
        data = json.loads(raw_payload)
        print(f"\n[✓] Detection event received on '{msg.topic}':")
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print(f"[!] Received non-JSON payload: {raw_payload}")

def main():
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    else:
        client = mqtt.Client()

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    print("[*] Waiting for incoming drone detection events (Press Ctrl+C to stop)...")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[*] Listener stopped.")
        client.disconnect()

if __name__ == "__main__":
    main()

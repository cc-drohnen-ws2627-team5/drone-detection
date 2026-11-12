import base64
import io
import json
import uuid
from datetime import datetime, timezone

import boto3
from botocore.client import Config
import paho.mqtt.client as mqtt
import psycopg2

# MQTT Configuration
BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC = "drone/detections"

# PostgreSQL Configuration
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "drone_db"
DB_USER = "drone_user"
DB_PASS = "drone_password"

# MinIO S3 Configuration
MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
BUCKET_NAME = "drone-snapshots"


def init_s3_client():
    s3 = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    existing_buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if BUCKET_NAME not in existing_buckets:
        s3.create_bucket(Bucket=BUCKET_NAME)
        print(f"[+] Created the '{BUCKET_NAME}' bucket in MinIO")
    return s3


def init_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )
    conn.autocommit = True
    return conn


def process_snapshot(s3_client, payload):
    image_b64 = payload.get("image_base64")
    if image_b64:
        image_bytes = base64.b64decode(image_b64)
        drone_id = payload.get("drone_id", "unknown-drone")
        timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        object_key = f"{drone_id}/{timestamp_slug}_{uuid.uuid4().hex[:8]}.jpg"

        s3_client.upload_fileobj(
            io.BytesIO(image_bytes),
            BUCKET_NAME,
            object_key,
            ExtraArgs={"ContentType": "image/jpeg"},
        )
        return f"{BUCKET_NAME}/{object_key}"

    return payload.get("image_url", f"{BUCKET_NAME}/test_frame.jpg")


def insert_detection(db_conn, payload, image_url):
    query = """
        INSERT INTO detections (drone_id, confidence, status, image_url, detected_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """
    detected_at = payload.get("detected_at") or datetime.now(timezone.utc).isoformat()
    values = (
        payload["drone_id"],
        float(payload["confidence"]),
        payload["status"],
        image_url,
        detected_at,
    )
    with db_conn.cursor() as cur:
        cur.execute(query, values)
        record_id = cur.fetchone()[0]
    return record_id


def main():
    print("[*] Initializing the MinIO S3 client and the PostgreSQL connection...")
    s3_client = init_s3_client()
    db_conn = init_db_connection()
    print("[+] Connected to MinIO and PostgreSQL")

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"[+] Connected to the Mosquitto broker at {BROKER_HOST}:{BROKER_PORT}")
            client.subscribe(TOPIC, qos=1)
            print(f"[*] Subscribed to the '{TOPIC}' topic")
        else:
            print(f"[-] Broker connection failed with the return code: {rc}")

    def on_message(client, userdata, msg):
        nonlocal db_conn
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            if db_conn.closed:
                db_conn = init_db_connection()

            image_url = process_snapshot(s3_client, payload)
            record_id = insert_detection(db_conn, payload, image_url)
            print(
                f"[✓] Persisted detection #{record_id} | "
                f"drone={payload['drone_id']} | "
                f"confidence={payload['confidence']} | "
                f"image={image_url}"
            )
        except (json.JSONDecodeError, KeyError, ValueError) as err:
            print(f"[!] Invalid detection payload skipped: {err}")
        except Exception as err:
            print(f"[-] Ingestion error: {err}")

    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    else:
        client = mqtt.Client()

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

    print("[*] Ingestion worker running (Press Ctrl+C to stop)...")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[*] Stopping the ingestion worker...")
        client.disconnect()
        db_conn.close()


if __name__ == "__main__":
    main()

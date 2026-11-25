import os
from contextlib import contextmanager
from functools import lru_cache

import boto3
import psycopg2
from botocore.config import Config
from botocore.exceptions import ClientError
from psycopg2.extras import Json, RealDictCursor

from .settings import BUCKET, required


class EventConflict(ValueError):
    pass


@contextmanager
def database():
    connection = psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres-db"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "drone_db"),
        user=required("DB_USER"),
        password=required("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "prefer"),
        sslrootcert=os.getenv("DB_SSLROOTCERT"),
        connect_timeout=4,
        options="-c statement_timeout=6000 -c lock_timeout=4000",
    )
    try:
        with connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
            yield cursor
    finally:
        connection.close()


@lru_cache
def object_store():
    return boto3.client(
        "s3",
        endpoint_url=required("S3_ENDPOINT"),
        aws_access_key_id=required("S3_ACCESS_KEY"),
        aws_secret_access_key=required("S3_SECRET_KEY"),
        verify=os.getenv("S3_CA_FILE") or True,
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=3,
            read_timeout=6,
            retries={"total_max_attempts": 1},
        ),
    )


def ensure_bucket():
    try:
        object_store().head_bucket(Bucket=BUCKET)
    except ClientError as error:
        if error.response["Error"]["Code"] not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        try:
            object_store().create_bucket(Bucket=BUCKET)
        except ClientError as race:
            if race.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
                raise


def persist(parsed):
    event, event_id, digest, image, video = parsed
    with database() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (event_id,))
        cursor.execute("SELECT payload_hash FROM detections WHERE event_id = %s", (event_id,))
        existing = cursor.fetchone()
        if existing:
            if existing["payload_hash"] != digest:
                raise EventConflict("event_id already used for a different payload")
            return False

        image_url = event.image_url
        video_key = None
        if image is not None:
            key = f"events/{event_id}/{digest}.jpg"
            object_store().put_object(Bucket=BUCKET, Key=key, Body=image, ContentType="image/jpeg")
            image_url = f"{BUCKET}/{key}"
        if video is not None:
            video_key = f"events/{event_id}/{digest}.mp4"
            object_store().put_object(Bucket=BUCKET, Key=video_key, Body=video, ContentType="video/mp4")
        cursor.execute(
            """
            INSERT INTO detections
                (event_id, payload_hash, drone_id, confidence, status, detected_at,
                 sensor_id, metadata, image_url, video_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (event_id, digest, event.drone_id, event.confidence, event.status,
             event.detected_at, event.sensor_id, Json(event.metadata), image_url, video_key),
        )
    return True

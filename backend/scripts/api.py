import logging
import secrets
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

import psycopg2
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

from .settings import BUCKET, required
from .storage import database, object_store

app = FastAPI(title="Drone Detection API")
LOG = logging.getLogger(__name__)
health_gauge = Gauge("drone_backend_ready", "PostgreSQL and S3 are reachable")
bearer = HTTPBearer(auto_error=False)
COLUMNS = "id, event_id, drone_id, confidence, status, detected_at, sensor_id, metadata, image_url, video_key"


def authorize(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode(), required("API_TOKEN").encode()
    ):
        raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})


@app.exception_handler(psycopg2.Error)
@app.exception_handler(BotoCoreError)
@app.exception_handler(ClientError)
async def unavailable(request: Request, error):
    LOG.warning("Dependency failed (%s)", type(error).__name__)
    return Response(status_code=503, headers={"Retry-After": "5"})


@app.get("/health/live")
def live():
    return {"status": "alive"}


def ready():
    with database() as cursor:
        cursor.execute("SELECT event_id FROM detections LIMIT 1")
    object_store().head_bucket(Bucket=BUCKET)


@app.get("/health/ready")
def readiness():
    ready()
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False, dependencies=[Depends(authorize)])
def metrics():
    try:
        ready()
    except (psycopg2.Error, BotoCoreError, ClientError):
        health_gauge.set(0)
    else:
        health_gauge.set(1)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def get_row(cursor, identifier):
    try:
        event_id = UUID(identifier)
    except ValueError:
        if not identifier.isascii() or not identifier.isdecimal() or len(identifier) > 10:
            raise HTTPException(404, "Detection not found")
        numeric_id = int(identifier)
        if numeric_id > 2147483647:
            raise HTTPException(404, "Detection not found")
        cursor.execute(f"SELECT {COLUMNS} FROM detections WHERE id = %s", (numeric_id,))
    else:
        cursor.execute(f"SELECT {COLUMNS} FROM detections WHERE event_id = %s", (str(event_id),))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(404, "Detection not found")
    return row


def present(row):
    prefix = f"/api/v1/detections/{row['id']}"
    row["image_path"] = f"{prefix}/image" if (row["image_url"] or "").startswith(f"{BUCKET}/") else None
    row["video_path"] = f"{prefix}/video" if row.pop("video_key") else None
    return row


@app.get("/api/v1/detections", dependencies=[Depends(authorize)])
def detections(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_id: Annotated[int | None, Query(ge=1, le=2147483647)] = None,
    drone_id: Annotated[str | None, Query(max_length=50)] = None,
    sensor_id: Annotated[str | None, Query(max_length=100)] = None,
    since: datetime | None = None,
):
    filters = []
    params = []
    for column, op, value in (
        ("id", "<", before_id), ("drone_id", "=", drone_id),
        ("sensor_id", "=", sensor_id), ("detected_at", ">=", since),
    ):
        if value is not None:
            if isinstance(value, str) and "\x00" in value:
                raise HTTPException(422, "Invalid filter")
            if isinstance(value, datetime) and value.utcoffset() is None:
                raise HTTPException(422, "since must include a time zone")
            filters.append(f"{column} {op} %s")
            params.append(value)
    with database() as cursor:
        where = " WHERE " + " AND ".join(filters) if filters else ""
        cursor.execute(f"SELECT {COLUMNS} FROM detections{where} ORDER BY id DESC LIMIT %s", (*params, limit + 1))
        rows = cursor.fetchall()
    return {
        "items": [present(row) for row in rows[:limit]],
        "next_before_id": rows[limit - 1]["id"] if len(rows) > limit else None,
    }


@app.get("/api/v1/detections/{identifier}", dependencies=[Depends(authorize)])
def detection(identifier: str):
    with database() as cursor:
        return present(get_row(cursor, identifier))


@app.get("/api/v1/detections/{identifier}/{kind}", dependencies=[Depends(authorize)])
def media(identifier: str, kind: str):
    with database() as cursor:
        row = get_row(cursor, identifier)
    if kind == "image" and (row["image_url"] or "").startswith(f"{BUCKET}/"):
        key = row["image_url"].split("/", 1)[1]
        content_type = "image/jpeg"
    elif kind == "video" and row["video_key"]:
        key = row["video_key"]
        content_type = "video/mp4"
    else:
        raise HTTPException(404, "Media not found")
    if not key:
        raise HTTPException(404, "Media not found")
    try:
        obj = object_store().get_object(Bucket=BUCKET, Key=key)
    except ClientError as error:
        if error.response["Error"]["Code"] in {"NoSuchKey", "404", "NotFound"}:
            raise HTTPException(404, "Media not found") from error
        raise

    def chunks():
        with closing(obj["Body"]) as body:
            yield from body.iter_chunks(chunk_size=64 * 1024)

    return StreamingResponse(chunks(), media_type=content_type, headers={
        "Content-Length": str(obj["ContentLength"]),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    })


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(Path(__file__).with_name("dashboard.html"), headers={
        "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src blob:; media-src blob:; frame-ancestors 'none'",
        "Referrer-Policy": "no-referrer",
    })

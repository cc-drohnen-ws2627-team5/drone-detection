import base64
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, field_validator

from .settings import MAX_IMAGE_BYTES, MAX_PACKET_BYTES, MAX_VIDEO_BYTES


class Detection(BaseModel):
    event_id: UUID | None = None
    drone_id: str = Field(min_length=1, max_length=50)
    confidence: float = Field(ge=0, le=1)
    status: str = Field(min_length=1, max_length=50)
    detected_at: AwareDatetime | None = None
    image_url: str | None = Field(default=None, max_length=2048)
    image_base64: str | None = None
    video_base64: str | None = None
    sensor_id: str | None = Field(default=None, min_length=1, max_length=100)
    metadata: dict = Field(default_factory=dict)

    @field_validator("drone_id", "status", "sensor_id", "image_url")
    @classmethod
    def validate_text(cls, value):
        if value is not None and ("\x00" in value or not value.strip()):
            raise ValueError("invalid text field")
        return value


def decode_media(encoded, limit, kind):
    if encoded is None:
        return None
    if len(encoded) > 4 * ((limit + 2) // 3):
        raise ValueError("media exceeds size limit")
    value = base64.b64decode(encoded, validate=True)
    if not value or len(value) > limit:
        raise ValueError("invalid media length")
    if kind == "jpeg" and not (value.startswith(b"\xff\xd8\xff") and value.endswith(b"\xff\xd9")):
        raise ValueError("expected JPEG")
    if kind == "mp4" and value[4:8] != b"ftyp":
        raise ValueError("expected MP4")
    return value


def parse_event(raw, received_at=None):
    if len(raw) > MAX_PACKET_BYTES:
        raise ValueError("payload exceeds size limit")
    event = Detection.model_validate_json(raw)
    stable_fields = event.model_dump(mode="json", exclude={"event_id"})
    canonical = json.dumps(stable_fields, sort_keys=True, allow_nan=False)
    # PostgreSQL JSONB rejects null characters and unpaired surrogates.
    metadata = json.dumps(event.metadata, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(metadata) > 65536:
        raise ValueError("metadata exceeds size limit")
    if "\\u0000" in canonical.replace("\\\\", ""):
        raise ValueError("invalid null character")
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    event.detected_at = event.detected_at or received_at or datetime.now(timezone.utc)
    image = decode_media(event.image_base64, MAX_IMAGE_BYTES, "jpeg")
    video = decode_media(event.video_base64, MAX_VIDEO_BYTES, "mp4")
    return event, str(event.event_id or UUID(hex=digest[:32])), digest, image, video

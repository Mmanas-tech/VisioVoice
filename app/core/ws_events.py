"""WebSocket event emitter for Celery tasks.

Uses Redis pub/sub to communicate from Celery workers to the Socket.IO server,
since Celery workers run in separate processes and cannot access the ASGI server directly.
"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _publish_event(channel: str, event: str, data: Dict[str, Any]):
    """Publish an event to Redis for the Socket.IO server to consume."""
    try:
        from app.config import get_settings
        import redis as redis_lib

        settings = get_settings()
        client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        payload = json.dumps({"event": event, "data": data})
        client.publish(channel, payload)
        client.close()
    except Exception as e:
        logger.warning(f"Failed to publish WebSocket event: {e}")


def emit_transcription_progress(transcription_id: str, progress: int, message: str):
    """Publish transcription progress event via Redis."""
    _publish_event(
        f"ws:transcription:{transcription_id}",
        "transcription_progress",
        {"transcription_id": transcription_id, "progress": progress, "message": message},
    )


def emit_audio_progress(transcription_id: str, progress: int, message: str):
    """Publish audio synthesis progress event via Redis."""
    _publish_event(
        f"ws:transcription:{transcription_id}",
        "audio_progress",
        {"transcription_id": transcription_id, "progress": progress, "message": message},
    )


def emit_transcription_complete(transcription_id: str, result: Dict[str, Any]):
    """Publish transcription completion event via Redis."""
    _publish_event(
        f"ws:transcription:{transcription_id}",
        "transcription_complete",
        {"transcription_id": transcription_id, **result},
    )


def emit_audio_complete(transcription_id: str, result: Dict[str, Any]):
    """Publish audio synthesis completion event via Redis."""
    _publish_event(
        f"ws:transcription:{transcription_id}",
        "audio_complete",
        {"transcription_id": transcription_id, **result},
    )


def emit_error(transcription_id: str, error: str):
    """Publish error event via Redis."""
    _publish_event(
        f"ws:transcription:{transcription_id}",
        "error",
        {"transcription_id": transcription_id, "error": error},
    )

"""WebSocket manager for real-time progress updates."""

import json
import logging
import socketio
from typing import Optional

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid: str, environ: dict, auth: Optional[dict] = None):
    """Handle new WebSocket connection."""
    token = auth.get("token") if auth else None
    if not token:
        logger.debug(f"WebSocket connection without auth: {sid}")
        await sio.emit("connected", {"status": "authenticated"}, room=sid)
        return

    try:
        from app.core.security import decode_token
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id:
            await sio.enter_room(sid, f"user:{user_id}")
            logger.info(f"User {user_id} connected via WebSocket (sid={sid})")
        await sio.emit("connected", {"status": "authenticated", "user_id": user_id}, room=sid)
    except Exception as e:
        logger.debug(f"WebSocket auth failed: {e}")
        await sio.emit("connected", {"status": "anonymous"}, room=sid)


@sio.event
async def disconnect(sid: str):
    """Handle WebSocket disconnection."""
    logger.debug(f"WebSocket disconnected: {sid}")


@sio.event
async def join_transcription(sid: str, data: dict):
    """Join a transcription progress room."""
    transcription_id = data.get("transcription_id")
    if transcription_id:
        room = f"transcription:{transcription_id}"
        await sio.enter_room(sid, room)
        logger.debug(f"Client {sid} joined room {room}")
        await sio.emit("joined", {"room": room}, room=sid)


@sio.event
async def leave_transcription(sid: str, data: dict):
    """Leave a transcription progress room."""
    transcription_id = data.get("transcription_id")
    if transcription_id:
        room = f"transcription:{transcription_id}"
        await sio.leave_room(sid, room)
        logger.debug(f"Client {sid} left room {room}")


async def emit_transcription_progress(transcription_id: str, progress: int, message: str):
    """Emit transcription progress to all subscribers."""
    room = f"transcription:{transcription_id}"
    await sio.emit(
        "transcription_progress",
        {"transcription_id": transcription_id, "progress": progress, "message": message},
        room=room,
    )


async def emit_audio_progress(transcription_id: str, progress: int, message: str):
    """Emit audio synthesis progress to all subscribers."""
    room = f"transcription:{transcription_id}"
    await sio.emit(
        "audio_progress",
        {"transcription_id": transcription_id, "progress": progress, "message": message},
        room=room,
    )


async def emit_transcription_complete(transcription_id: str, result: dict):
    """Emit transcription completion event."""
    room = f"transcription:{transcription_id}"
    await sio.emit(
        "transcription_complete",
        {"transcription_id": transcription_id, **result},
        room=room,
    )


async def emit_audio_complete(transcription_id: str, result: dict):
    """Emit audio synthesis completion event."""
    room = f"transcription:{transcription_id}"
    await sio.emit(
        "audio_complete",
        {"transcription_id": transcription_id, **result},
        room=room,
    )


async def emit_error(transcription_id: str, error: str):
    """Emit error event."""
    room = f"transcription:{transcription_id}"
    await sio.emit(
        "error",
        {"transcription_id": transcription_id, "error": error},
        room=room,
    )


async def redis_listener():
    """Listen for Redis pub/sub events and forward to Socket.IO rooms."""
    import asyncio
    try:
        from app.config import get_settings
        settings = get_settings()
        import redis.asyncio as aioredis

        pubsub_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = pubsub_client.pubsub()

        pattern = "ws:transcription:*"
        await pubsub.psubscribe(pattern)
        logger.info(f"Redis WebSocket listener started on pattern: {pattern}")

        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    channel = message["channel"]
                    data = json.loads(message["data"])
                    event = data.get("event")
                    event_data = data.get("data", {})

                    transcription_id = event_data.get("transcription_id")
                    if transcription_id:
                        room = f"transcription:{transcription_id}"
                        await sio.emit(event, event_data, room=room)
                except Exception as e:
                    logger.debug(f"Error processing Redis message: {e}")
    except Exception as e:
        logger.warning(f"Redis listener failed: {e}")

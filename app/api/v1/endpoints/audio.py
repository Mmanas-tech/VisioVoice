"""Audio synthesis API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.exceptions import NotFoundError, TranscriptionError
from app.db.database import get_sync_db_session
from app.models.database import Transcription, User, Video
from app.models.schemas import MessageResponse
from app.tasks.audio_synthesis_tasks import synthesize_audio_for_transcription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audio", tags=["Audio Synthesis"])


@router.post("/synthesize/{transcription_id}", status_code=202)
def request_audio_synthesis(
    transcription_id: str,
    tts_backend: str = Query("pyttsx3", pattern=r"^(pyttsx3|google|bark|elevenlabs)$"),
    language: str = Query("en-US"),
    voice: str = Query("default"),
    pitch: float = Query(0.0, ge=-20.0, le=20.0),
    speaking_rate: float = Query(1.0, ge=0.25, le=4.0),
    export_formats: str = Query("wav,mp3"),
    enable_enhancement: bool = Query(True),
    enable_lipsync: bool = Query(True),
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Request audio synthesis from a completed transcription.

    Generates speech audio from the transcription text and aligns it
    with the original video timing.
    """
    transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
    if not transcription:
        raise NotFoundError(resource="Transcription", resource_id=transcription_id)

    video = db.query(Video).filter(Video.id == transcription.video_id).first()
    if not video:
        raise NotFoundError(resource="Video", resource_id=transcription.video_id)

    if video.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Not authorized")

    if transcription.status != "completed":
        raise TranscriptionError(message="Transcription must be completed before audio synthesis")

    formats = [f.strip() for f in export_formats.split(",") if f.strip()]

    voice_params = {
        "language": language,
        "voice": voice,
        "pitch": pitch,
        "speaking_rate": speaking_rate,
    }

    task = synthesize_audio_for_transcription.apply_async(
        args=[transcription_id, video.id],
        kwargs={
            "tts_backend": tts_backend,
            "voice_params": voice_params,
            "export_formats": formats,
            "enable_enhancement": enable_enhancement,
            "enable_lipsync": enable_lipsync,
        },
    )

    logger.info(f"Audio synthesis requested for transcription {transcription_id}")

    return {
        "transcription_id": transcription_id,
        "status": "queued",
        "job_id": task.id,
        "tts_backend": tts_backend,
        "formats": formats,
    }


@router.get("/synthesize/{transcription_id}/status")
def get_synthesis_status(
    transcription_id: str,
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get audio synthesis status and progress."""
    transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
    if not transcription:
        raise NotFoundError(resource="Transcription", resource_id=transcription_id)

    video = db.query(Video).filter(Video.id == transcription.video_id).first()
    if video and video.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Not authorized")

    details = transcription.details_json if isinstance(transcription.details_json, dict) else {}
    audio_info = details.get("audio_synthesis", {})

    return {
        "transcription_id": transcription_id,
        "audio_synthesis_status": audio_info.get("status", "not_started"),
        "audio_files": audio_info.get("audio_files", {}),
        "subtitle_files": audio_info.get("subtitle_files", {}),
        "audio_duration": audio_info.get("audio_duration"),
        "processing_time": audio_info.get("processing_time"),
    }


@router.get("/synthesize/{transcription_id}/download/{format}")
def download_synthesized_audio(
    transcription_id: str,
    format: str = Path(..., pattern=r"^(wav|mp3|flac|aac|ogg)$"),
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Download synthesized audio file."""
    transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
    if not transcription:
        raise NotFoundError(resource="Transcription", resource_id=transcription_id)

    video = db.query(Video).filter(Video.id == transcription.video_id).first()
    if video and video.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Not authorized")

    details = transcription.details_json if isinstance(transcription.details_json, dict) else {}
    audio_info = details.get("audio_synthesis", {})
    audio_files = audio_info.get("audio_files", {})

    file_path = audio_files.get(format)
    if not file_path:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(resource=f"Audio file ({format})", resource_id=transcription_id)

    import os
    if not os.path.exists(file_path):
        from app.core.exceptions import NotFoundError
        raise NotFoundError(resource="Audio file on disk", resource_id=transcription_id)

    media_types = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "flac": "audio/flac",
        "aac": "audio/aac",
        "ogg": "audio/ogg",
    }

    return FileResponse(
        path=file_path,
        filename=f"transcription_{transcription_id}.{format}",
        media_type=media_types.get(format, "application/octet-stream"),
    )


@router.get("/synthesize/{transcription_id}/subtitle/{format}")
def download_subtitle(
    transcription_id: str,
    format: str = Path(..., pattern=r"^(srt|vtt|ass)$"),
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Download generated subtitle file."""
    transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
    if not transcription:
        raise NotFoundError(resource="Transcription", resource_id=transcription_id)

    video = db.query(Video).filter(Video.id == transcription.video_id).first()
    if video and video.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Not authorized")

    details = transcription.details_json if isinstance(transcription.details_json, dict) else {}
    subtitle_files = details.get("audio_synthesis", {}).get("subtitle_files", {})

    file_path = subtitle_files.get(format)
    if not file_path:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(resource=f"Subtitle file ({format})", resource_id=transcription_id)

    import os
    if not os.path.exists(file_path):
        from app.core.exceptions import NotFoundError
        raise NotFoundError(resource="Subtitle file on disk", resource_id=transcription_id)

    media_types = {"srt": "application/x-subrip", "vtt": "text/vtt", "ass": "text/x-ass"}

    return FileResponse(
        path=file_path,
        filename=f"transcription_{transcription_id}.{format}",
        media_type=media_types.get(format, "text/plain"),
    )


@router.get("/backends")
def list_tts_backends():
    """List available TTS backends."""
    from app.ml.audio.tts_service import TextToSpeechService
    tts = TextToSpeechService.__new__(TextToSpeechService)
    tts._engine = None
    tts._client = None
    tts._bark_ready = False
    try:
        import pyttsx3
        tts._engine = pyttsx3.init()
    except (ImportError, RuntimeError) as exc:
        logger.debug(f"pyttsx3 not available: {exc}")

    return {
        "available_backends": tts.available_backends,
        "default_backend": "pyttsx3",
        "backends": {
            "pyttsx3": {"name": "pyttsx3", "type": "local", "quality": "basic"},
            "google": {"name": "Google Cloud TTS", "type": "cloud", "quality": "high"},
            "bark": {"name": "Bark", "type": "local", "quality": "high"},
            "elevenlabs": {"name": "ElevenLabs", "type": "cloud", "quality": "premium"},
        },
    }

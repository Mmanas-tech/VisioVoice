"""Transcription endpoints."""

import logging
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.exceptions import NotFoundError, TranscriptionError
from app.db.database import get_sync_db_session
from app.models.database import Transcription, User, Video
from app.models.schemas import (
    BatchTranscriptionRequest,
    BatchTranscriptionResponse,
    MessageResponse,
    TranscriptionDetailResponse,
    TranscriptionJobResponse,
    TranscriptionRequest,
    TranscriptionResponse,
)
from app.services.transcription_service import TranscriptionService
from app.tasks.celery_app import celery_app
from app.tasks.transcription_tasks import process_video_transcription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcriptions", tags=["Transcriptions"])

transcription_service = TranscriptionService()


@router.post("/process", response_model=TranscriptionJobResponse, status_code=202)
def request_transcription(
    body: TranscriptionRequest,
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Submit a video for transcription processing."""
    video = db.query(Video).filter(Video.id == body.video_id, Video.is_deleted == False).first()
    if not video:
        raise NotFoundError(resource="Video", resource_id=body.video_id)
    if video.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Not authorized to transcribe this video")

    transcription = transcription_service.create_transcription(db, body.video_id)

    video.status = "processing"
    db.commit()

    priority = 1 if body.priority == "high" else 5
    task = process_video_transcription.apply_async(
        args=[video.id, transcription.id, body.language, body.include_timestamps],
        priority=priority,
    )

    estimated_time = transcription_service.calculate_estimated_time(video.duration or 60)

    logger.info(f"Transcription job submitted: {transcription.id} for video {body.video_id}")

    return TranscriptionJobResponse(
        transcription_id=transcription.id,
        video_id=body.video_id,
        status="queued",
        estimated_processing_time_seconds=estimated_time,
        job_id=task.id,
    )


@router.get("/{transcription_id}", response_model=TranscriptionDetailResponse)
def get_transcription(
    transcription_id: str,
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get transcription with all segments."""
    transcription = transcription_service.get_transcription(db, transcription_id)

    video = db.query(Video).filter(Video.id == transcription.video_id).first()
    if video and video.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Not authorized to view this transcription")

    return TranscriptionDetailResponse.model_validate(transcription)


@router.get("/{transcription_id}/status")
def get_transcription_status(
    transcription_id: str,
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get lightweight transcription status."""
    transcription = transcription_service.get_transcription(db, transcription_id)
    return {
        "transcription_id": transcription.id,
        "status": transcription.status,
        "progress": transcription.progress,
        "error_message": transcription.error_message,
    }


@router.get("/{transcription_id}/export")
def export_transcription(
    transcription_id: str,
    format: str = Query("json", pattern=r"^(json|srt|vtt)$"),
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Export transcription in various formats."""
    transcription = transcription_service.get_transcription(db, transcription_id)

    video = db.query(Video).filter(Video.id == transcription.video_id).first()
    if video and video.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Not authorized")

    if format == "json":
        return TranscriptionDetailResponse.model_validate(transcription)
    elif format == "srt":
        srt_content = transcription_service.export_srt(transcription)
        return PlainTextResponse(content=srt_content, media_type="application/x-subrip")
    elif format == "vtt":
        vtt_content = transcription_service.export_vtt(transcription)
        return PlainTextResponse(content=vtt_content, media_type="text/vtt")


@router.delete("/{transcription_id}", response_model=MessageResponse)
def delete_transcription(
    transcription_id: str,
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a transcription."""
    transcription = transcription_service.get_transcription(db, transcription_id)
    video = db.query(Video).filter(Video.id == transcription.video_id).first()
    if video and video.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Not authorized")

    transcription_service.delete_transcription(db, transcription_id)
    db.commit()
    return MessageResponse(message="Transcription deleted")


@router.post("/batch-process", response_model=BatchTranscriptionResponse, status_code=202)
def batch_process_transcriptions(
    body: BatchTranscriptionRequest,
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Submit multiple videos for transcription."""
    jobs = []
    for video_id in body.video_ids:
        video = db.query(Video).filter(Video.id == video_id, Video.is_deleted == False).first()
        if not video or (video.user_id != current_user.id and not current_user.is_admin):
            continue

        transcription = transcription_service.create_transcription(db, video_id)
        video.status = "processing"

        task = process_video_transcription.apply_async(
            args=[video.id, transcription.id, "en", True],
        )

        estimated_time = transcription_service.calculate_estimated_time(video.duration or 60)
        jobs.append(TranscriptionJobResponse(
            transcription_id=transcription.id,
            video_id=video_id,
            status="queued",
            estimated_processing_time_seconds=estimated_time,
            job_id=task.id,
        ))

    db.commit()
    return BatchTranscriptionResponse(jobs=jobs)

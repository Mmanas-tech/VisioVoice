"""Video management endpoints."""

import logging
import math
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.exceptions import (
    FileTooLargeError,
    NotFoundError,
    UnsupportedFileTypeError,
    ValidationError,
)
from app.db.database import get_sync_db_session
from app.models.database import User, Video
from app.models.schemas import VideoListResponse, VideoResponse, VideoUploadResponse
from app.services.video_service import VideoService
from app.tasks.celery_app import celery_app
from app.tasks.transcription_tasks import process_video_transcription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/videos", tags=["Videos"])

video_service = VideoService()


@router.post("/upload", response_model=VideoUploadResponse, status_code=201)
async def upload_video(
    request: Request,
    video_file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Upload a video file for lip-reading transcription."""
    if not video_file.filename:
        raise ValidationError(message="No file provided")

    ext = "." + video_file.filename.rsplit(".", 1)[-1].lower() if "." in video_file.filename else ""
    if ext not in [".mp4", ".mov", ".avi", ".mkv"]:
        raise UnsupportedFileTypeError(file_type=ext, allowed=[".mp4", ".mov", ".avi", ".mkv"])

    file_content = await video_file.read()
    max_size = 2048 * 1024 * 1024
    if len(file_content) > max_size:
        raise FileTooLargeError(max_size_mb=2048)

    video_data = await video_service.save_uploaded_video(
        file_content=file_content,
        user_id=current_user.id,
        filename=video_file.filename,
        title=title,
    )

    video = Video(
        user_id=current_user.id,
        filename=video_data["filename"],
        original_filename=video_file.filename,
        title=video_data.get("title"),
        description=description,
        file_size=video_data["file_size"],
        duration=video_data.get("duration"),
        fps=video_data.get("fps"),
        resolution=video_data.get("resolution"),
        codec=video_data.get("codec"),
        storage_path=video_data["storage_path"],
        status="uploaded",
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    logger.info(f"Video uploaded: {video.id} by user {current_user.username}")

    return VideoUploadResponse(
        id=video.id,
        filename=video.filename,
        original_filename=video.original_filename,
        title=video.title,
        size=video.file_size,
        status=video.status,
        processing_scheduled=False,
        created_at=video.created_at,
    )


@router.get("", response_model=VideoListResponse)
def list_videos(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    sort_by: str = Query("created_at", pattern=r"^(created_at|size|title)$"),
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """List all videos for the current user."""
    query = db.query(Video).filter(Video.user_id == current_user.id, Video.is_deleted == False)

    if status:
        query = query.filter(Video.status == status)

    sort_column = getattr(Video, sort_by)
    query = query.order_by(sort_column.desc())

    total = query.count()
    pages = math.ceil(total / per_page)
    videos = query.offset((page - 1) * per_page).limit(per_page).all()

    return VideoListResponse(
        items=[VideoResponse.model_validate(v) for v in videos],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(
    video_id: str,
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get video details by ID."""
    video = db.query(Video).filter(Video.id == video_id, Video.is_deleted == False).first()
    if not video:
        raise NotFoundError(resource="Video", resource_id=video_id)
    if video.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Not authorized to view this video")
    return video


@router.delete("/{video_id}", status_code=204)
def delete_video(
    video_id: str,
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Soft delete a video."""
    video = db.query(Video).filter(Video.id == video_id, Video.is_deleted == False).first()
    if not video:
        raise NotFoundError(resource="Video", resource_id=video_id)
    if video.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Not authorized to delete this video")

    video.is_deleted = True
    video.status = "deleted"
    db.commit()

    logger.info(f"Video soft deleted: {video_id}")
    return None


@router.get("/{video_id}/download")
def download_video(
    video_id: str,
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Download a video file."""
    video = db.query(Video).filter(Video.id == video_id, Video.is_deleted == False).first()
    if not video:
        raise NotFoundError(resource="Video", resource_id=video_id)
    if video.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Not authorized to download this video")

    from app.services.storage_service import StorageService
    storage = StorageService()
    file_path = storage.get_video_path(video.storage_path)

    return FileResponse(
        path=file_path,
        filename=video.original_filename,
        media_type="video/mp4",
    )

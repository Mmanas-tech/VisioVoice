"""Celery tasks for video transcription processing."""

import logging
import time
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def extract_frames(video_path: str, fps: int = 25, target_size: tuple = (224, 224)) -> np.ndarray:
    """Extract and preprocess frames from video."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = max(1, int(video_fps / fps))

    frames = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            resized = cv2.resize(frame, target_size)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            frames.append(rgb)
        frame_idx += 1

    cap.release()
    return np.array(frames) if frames else np.array([])


def detect_mouth_region(frames: np.ndarray) -> np.ndarray:
    """Detect and crop mouth region from frames (simplified)."""
    mouth_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_smile.xml")
    cropped_frames = []

    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        faces = mouth_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) > 0:
            x, y, w, h = faces[0]
            mouth_y = y + h // 2
            mouth_h = h // 2
            cropped = frame[max(0, mouth_y - mouth_h):mouth_y + mouth_h, x:x + w]
            cropped = cv2.resize(cropped, (224, 224))
            cropped_frames.append(cropped)
        else:
            cropped_frames.append(frame)

    return np.array(cropped_frames) if cropped_frames else frames


def normalize_frames(frames: np.ndarray) -> np.ndarray:
    """Normalize frames for model input."""
    normalized = frames.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406])
    std = np.array([0.229, 0.224, 0.225])
    normalized = (normalized - mean) / std
    return normalized


def post_process_output(raw_text: str) -> str:
    """Clean and format model output text."""
    import re
    cleaned = re.sub(r'\s+', ' ', raw_text).strip()
    cleaned = re.sub(r'[^\w\s.,!?;:\'-]', '', cleaned)
    if cleaned and not cleaned[0].isupper():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def create_segments(text: str, total_duration_ms: int, segment_duration_ms: int = 5000) -> List[Dict[str, Any]]:
    """Split text into timed segments."""
    words = text.split()
    if not words:
        return []

    words_per_segment = max(1, len(words) * segment_duration_ms // total_duration_ms)
    segments = []

    for i in range(0, len(words), words_per_segment):
        segment_words = words[i:i + words_per_segment]
        start_ms = int(i * total_duration_ms / len(words))
        end_ms = int(min(i + words_per_segment, len(words)) * total_duration_ms / len(words))

        segments.append({
            "segment_index": len(segments),
            "start_time_ms": start_ms,
            "end_time_ms": end_ms,
            "text": " ".join(segment_words),
            "confidence_score": 0.85,
        })

    return segments


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_video_transcription(
    self,
    video_id: str,
    transcription_id: str,
    language: str = "en",
    include_timestamps: bool = True,
) -> Dict[str, Any]:
    """
    Main transcription task.
    Processes video through lip-reading pipeline and saves results.
    """
    from app.config import get_settings
    from app.db.database import SessionLocal
    from app.models.database import Transcription, Video
    from app.services.model_service import model_service
    from app.services.transcription_service import TranscriptionService
    from app.services.storage_service import StorageService

    settings = get_settings()
    transcription_service = TranscriptionService()
    storage_service = StorageService()
    db = SessionLocal()

    start_time = time.time()

    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video not found: {video_id}")

        transcription_service.update_status(db, transcription_id, "processing", 10)
        db.commit()

        file_path = storage_service.get_video_path(video.storage_path)

        transcription_service.update_status(db, transcription_id, "processing", 20)
        db.commit()

        frames = extract_frames(file_path)
        if len(frames) == 0:
            raise ValueError("No frames could be extracted from video")

        transcription_service.update_status(db, transcription_id, "processing", 40)
        db.commit()

        frames = detect_mouth_region(frames)

        transcription_service.update_status(db, transcription_id, "processing", 50)
        db.commit()

        frames = normalize_frames(frames)

        transcription_service.update_status(db, transcription_id, "processing", 60)
        db.commit()

        model_result = model_service.predict(frames, language)

        transcription_service.update_status(db, transcription_id, "processing", 80)
        db.commit()

        cleaned_text = post_process_output(model_result["raw_transcript"])

        total_duration_ms = int((video.duration or 0) * 1000)
        segments = create_segments(cleaned_text, total_duration_ms) if include_timestamps else []

        processing_time = time.time() - start_time

        result = {
            "raw_transcript": model_result["raw_transcript"],
            "cleaned_transcript": cleaned_text,
            "confidence_score": model_result["confidence_score"],
            "processing_time_seconds": round(processing_time, 2),
            "model_version": "1.0.0",
            "language_detected": language,
            "segments": segments,
        }

        transcription_service.save_result(db, transcription_id, result)

        video.status = "processed"
        db.commit()

        logger.info(f"Transcription completed: {transcription_id} in {processing_time:.2f}s")

        return {
            "transcription_id": transcription_id,
            "status": "completed",
            "processing_time_seconds": round(processing_time, 2),
        }

    except Exception as e:
        logger.error(f"Transcription failed: {transcription_id}, error: {str(e)}")
        try:
            transcription_service.update_status(db, transcription_id, "failed", error_message=str(e))
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.status = "failed"
            db.commit()
        except Exception:
            db.rollback()

        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task
def cleanup_old_videos():
    """Clean up old soft-deleted videos (older than 30 days)."""
    from datetime import datetime, timedelta, timezone
    from app.db.database import SessionLocal
    from app.models.database import Video
    from app.services.storage_service import StorageService

    db = SessionLocal()
    storage = StorageService()

    try:
        threshold = datetime.now(timezone.utc) - timedelta(days=30)
        old_videos = db.query(Video).filter(
            Video.is_deleted == True,
            Video.updated_at < threshold,
        ).all()

        for video in old_videos:
            storage.delete_video(video.storage_path)
            db.delete(video)

        db.commit()
        logger.info(f"Cleaned up {len(old_videos)} old videos")
    finally:
        db.close()

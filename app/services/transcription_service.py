"""Transcription orchestration service."""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, TranscriptionError
from app.models.database import Transcription, TranscriptionSegment, Video
from app.services.model_service import model_service

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for managing transcription lifecycle."""

    def __init__(self):
        self.model = model_service

    def create_transcription(self, db: Session, video_id: str) -> Transcription:
        """Create a new transcription record for a video."""
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise NotFoundError(resource="Video", resource_id=video_id)

        existing = db.query(Transcription).filter(Transcription.video_id == video_id).first()
        if existing and existing.status in ("pending", "processing"):
            raise TranscriptionError(message="A transcription is already in progress for this video")

        if existing:
            db.delete(existing)
            db.flush()

        transcription = Transcription(video_id=video_id, status="pending", progress=0)
        db.add(transcription)
        db.flush()

        return transcription

    def update_status(
        self,
        db: Session,
        transcription_id: str,
        status: str,
        progress: int = 0,
        error_message: Optional[str] = None,
    ) -> Transcription:
        """Update transcription status."""
        transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if not transcription:
            raise NotFoundError(resource="Transcription", resource_id=transcription_id)

        transcription.status = status
        transcription.progress = progress
        if error_message:
            transcription.error_message = error_message
        db.flush()
        return transcription

    def save_result(
        self,
        db: Session,
        transcription_id: str,
        result: Dict[str, Any],
    ) -> Transcription:
        """Save transcription result with segments."""
        transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if not transcription:
            raise NotFoundError(resource="Transcription", resource_id=transcription_id)

        transcription.raw_transcript = result.get("raw_transcript", "")
        transcription.cleaned_transcript = result.get("cleaned_transcript", "")
        transcription.confidence_score = result.get("confidence_score", 0.0)
        transcription.processing_time_seconds = result.get("processing_time_seconds", 0.0)
        transcription.model_version = result.get("model_version", "1.0.0")
        transcription.language_detected = result.get("language_detected", "en")
        transcription.status = "completed"
        transcription.progress = 100

        for seg_data in result.get("segments", []):
            segment = TranscriptionSegment(
                transcription_id=transcription_id,
                segment_index=seg_data["segment_index"],
                start_time_ms=seg_data["start_time_ms"],
                end_time_ms=seg_data["end_time_ms"],
                text=seg_data["text"],
                confidence_score=seg_data.get("confidence_score", 0.0),
                speaker_label=seg_data.get("speaker_label"),
            )
            db.add(segment)

        db.flush()
        return transcription

    def get_transcription(self, db: Session, transcription_id: str) -> Transcription:
        """Get a transcription by ID."""
        transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if not transcription:
            raise NotFoundError(resource="Transcription", resource_id=transcription_id)
        return transcription

    def get_transcription_by_video(self, db: Session, video_id: str) -> Optional[Transcription]:
        """Get transcription for a video."""
        return db.query(Transcription).filter(Transcription.video_id == video_id).first()

    def delete_transcription(self, db: Session, transcription_id: str) -> bool:
        """Delete a transcription."""
        transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if not transcription:
            raise NotFoundError(resource="Transcription", resource_id=transcription_id)
        db.delete(transcription)
        db.flush()
        return True

    def calculate_estimated_time(self, duration_seconds: float) -> float:
        """Estimate transcription processing time based on video duration."""
        processing_ratio = 2.0
        return duration_seconds * processing_ratio

    def export_srt(self, transcription: Transcription) -> str:
        """Export transcription as SRT subtitle format."""
        lines = []
        for seg in sorted(transcription.segments, key=lambda s: s.segment_index):
            start = self._ms_to_srt_time(seg.start_time_ms)
            end = self._ms_to_srt_time(seg.end_time_ms)
            lines.append(f"{seg.segment_index + 1}")
            lines.append(f"{start} --> {end}")
            lines.append(seg.text)
            lines.append("")
        return "\n".join(lines)

    def export_vtt(self, transcription: Transcription) -> str:
        """Export transcription as WebVTT format."""
        lines = ["WEBVTT", ""]
        for seg in sorted(transcription.segments, key=lambda s: s.segment_index):
            start = self._ms_to_vtt_time(seg.start_time_ms)
            end = self._ms_to_vtt_time(seg.end_time_ms)
            lines.append(f"{start} --> {end}")
            lines.append(seg.text)
            lines.append("")
        return "\n".join(lines)

    def _ms_to_srt_time(self, ms: int) -> str:
        """Convert milliseconds to SRT timestamp format."""
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def _ms_to_vtt_time(self, ms: int) -> str:
        """Convert milliseconds to VTT timestamp format."""
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

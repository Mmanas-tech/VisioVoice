"""Celery tasks for audio synthesis from transcription output."""

import json
import logging
import os
import time
from typing import Any, Dict, Optional

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def update_synthesis_progress(transcription_id: str, progress: int, message: str):
    """Update audio synthesis progress in Redis."""
    try:
        from app.config import get_settings
        import redis as redis_lib

        settings = get_settings()
        client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        client.setex(
            f"audio_synthesis_progress:{transcription_id}",
            3600,
            json.dumps({"progress": progress, "message": message, "timestamp": time.time()}),
        )
        client.close()
    except Exception as e:
        logger.warning(f"Failed to update synthesis progress: {e}")

    logger.info(f"Audio synthesis progress [{transcription_id}]: {progress}% - {message}")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def synthesize_audio_for_transcription(
    self,
    transcription_id: str,
    video_id: str,
    tts_backend: str = "pyttsx3",
    voice_params: Optional[Dict] = None,
    export_formats: Optional[list] = None,
    enable_enhancement: bool = True,
    enable_lipsync: bool = True,
) -> Dict[str, Any]:
    """
    Celery task: Synthesize audio from transcription output.

    Pipeline:
    1. Load transcription and segments from DB
    2. Run TTS synthesis
    3. Apply audio enhancement
    4. Align with video timing
    5. Export in requested formats
    6. Generate subtitles
    7. Save results to DB/storage
    """
    start_time = time.time()

    try:
        from app.config import get_settings
        from app.db.database import SessionLocal
        from app.models.database import Transcription, TranscriptionSegment, Video
        from app.ml.audio.audio_pipeline import AudioSynthesisPipeline

        settings = get_settings()
        db = SessionLocal()

        transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        video = db.query(Video).filter(Video.id == video_id).first()

        if not transcription or not video:
            raise ValueError(f"Transcription {transcription_id} or Video {video_id} not found")

        update_synthesis_progress(transcription_id, 5, "Loading transcription data...")

        segments = (
            db.query(TranscriptionSegment)
            .filter(TranscriptionSegment.transcription_id == transcription_id)
            .order_by(TranscriptionSegment.segment_index)
            .all()
        )

        segments_data = [
            {
                "start_ms": s.start_time_ms,
                "end_ms": s.end_time_ms,
                "text": s.text,
                "segment_index": s.segment_index,
            }
            for s in segments
        ]

        update_synthesis_progress(transcription_id, 10, "Initializing TTS pipeline...")

        output_dir = os.path.join(settings.LOCAL_STORAGE_PATH, "audio_synthesis", transcription_id)
        os.makedirs(output_dir, exist_ok=True)

        pipeline = AudioSynthesisPipeline(
            tts_backend=tts_backend,
            enable_enhancement=enable_enhancement,
            enable_lipsync=enable_lipsync,
        )

        update_synthesis_progress(transcription_id, 15, "Starting audio synthesis...")

        voice_params = voice_params or {}
        export_formats = export_formats or ["wav", "mp3"]

        result = pipeline.synthesize_from_transcription(
            transcription_text=transcription.cleaned_transcript or transcription.raw_transcript or "",
            transcription_segments=segments_data,
            video_duration_seconds=video.duration or 0,
            video_fps=int(video.fps) if video.fps else 25,
            output_dir=output_dir,
            export_formats=export_formats,
            voice_params=voice_params,
            generate_subtitles=True,
        )

        update_synthesis_progress(transcription_id, 80, "Saving results...")

        audio_metadata = result["metadata"]
        audio_files = result["audio_files"]
        subtitle_files = result["subtitle_files"]

        if not hasattr(transcription, "details_json") or transcription.details_json is None:
            transcription.details_json = {}

        details = transcription.details_json if isinstance(transcription.details_json, dict) else {}
        details["audio_synthesis"] = {
            "status": "completed",
            "output_dir": output_dir,
            "audio_files": {fmt: info["path"] for fmt, info in audio_files.items()},
            "subtitle_files": subtitle_files,
            "audio_duration": audio_metadata["audio_duration_seconds"],
            "tts_backend": tts_backend,
            "enhancements": audio_metadata["enhancements_applied"],
            "processing_time": audio_metadata["total_processing_time_seconds"],
        }
        transcription.details_json = details
        db.commit()

        update_synthesis_progress(transcription_id, 100, "Audio synthesis completed!")

        total_time = time.time() - start_time
        logger.info(f"Audio synthesis completed for {transcription_id} in {total_time:.2f}s")

        return {
            "transcription_id": transcription_id,
            "status": "completed",
            "audio_files": {fmt: info["path"] for fmt, info in audio_files.items()},
            "subtitle_files": subtitle_files,
            "metadata": audio_metadata,
            "processing_time_seconds": round(total_time, 2),
        }

    except Exception as exc:
        logger.error(f"Audio synthesis failed: {transcription_id} - {str(exc)}", exc_info=True)

        try:
            from app.db.database import SessionLocal
            from app.models.database import Transcription
            db = SessionLocal()
            transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
            if transcription:
                details = transcription.details_json if isinstance(transcription.details_json, dict) else {}
                details["audio_synthesis"] = {"status": "failed", "error": str(exc)[:500]}
                transcription.details_json = details
                db.commit()
        except Exception:
            pass

        raise self.retry(exc=exc)


@celery_app.task
def synthesize_audio_batch(
    transcription_video_pairs: list,
    tts_backend: str = "pyttsx3",
    voice_params: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Batch audio synthesis for multiple transcriptions."""
    results = []
    for pair in transcription_video_pairs:
        try:
            result = synthesize_audio_for_transcription(
                transcription_id=pair["transcription_id"],
                video_id=pair["video_id"],
                tts_backend=tts_backend,
                voice_params=voice_params,
            )
            results.append(result)
        except Exception as e:
            results.append({
                "transcription_id": pair["transcription_id"],
                "status": "failed",
                "error": str(e),
            })

    return {"results": results, "total": len(results)}

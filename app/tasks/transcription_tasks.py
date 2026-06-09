"""Celery tasks for video transcription processing with full ML pipeline."""

import json
import logging
import os
import time
from typing import Any, Dict, Optional

import numpy as np

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def update_progress(transcription_id: str, progress: int, message: str):
    """Update transcription progress in Redis for real-time frontend updates."""
    try:
        from app.config import get_settings
        import redis as redis_lib

        settings = get_settings()
        client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        client.setex(
            f"transcription_progress:{transcription_id}",
            3600,
            json.dumps({"progress": progress, "message": message, "timestamp": time.time()}),
        )
        client.close()
    except Exception as e:
        logger.warning(f"Failed to update progress: {e}")

    logger.info(f"Progress [{transcription_id}]: {progress}% - {message}")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def process_video_transcription(
    self,
    video_id: str,
    transcription_id: str,
    language: str = "en",
    include_timestamps: bool = True,
) -> Dict[str, Any]:
    """
    Complete transcription pipeline:

    1. Load video from storage
    2. Preprocess frames (face detection, mouth extraction)
    3. Run lip-reading inference
    4. Generate timestamped segments
    5. NLP refinement
    6. Save results to database
    """
    start_time = time.time()

    from app.config import get_settings
    from app.db.database import SessionLocal
    from app.models.database import Transcription, TranscriptionSegment, Video
    from app.services.storage_service import StorageService

    settings = get_settings()
    db = SessionLocal()

    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if not video or not transcription:
            raise ValueError(f"Video {video_id} or Transcription {transcription_id} not found")

        transcription.status = "processing"
        transcription.progress = 5
        db.commit()

        storage_service = StorageService()
        video_path = storage_service.get_video_path(video.storage_path)

        update_progress(transcription_id, 10, "Extracting frames...")

        from app.ml.video_preprocessing import VideoPreprocessor
        from app.ml.preprocessing_config import PreprocessingConfig

        preprocessor = VideoPreprocessor(PreprocessingConfig())
        frames, metadata = preprocessor.preprocess_video_for_model(video_path)

        logger.info(f"Extracted {frames.shape[0]} valid frames from video {video_id}")

        update_progress(transcription_id, 30, "Running lip-reading inference...")

        from app.ml.model_manager import model_manager

        model = model_manager.load_model(
            model_name="lip_reading_v1",
            device=settings.MODEL_DEVICE,
            batch_size=32,
            use_fp16=True,
        )

        inference_result = model.infer_single_video(
            frames, return_confidence=True, return_logits=True
        )

        raw_text = inference_result["text"]
        logits = inference_result["logits"]
        confidence_scores = inference_result["confidence_scores"]
        character_texts = inference_result["characters"]

        avg_confidence = float(np.mean(confidence_scores)) if confidence_scores else 0.0
        logger.info(f"Raw transcription: '{raw_text}' | confidence: {avg_confidence:.3f}")

        update_progress(transcription_id, 55, "Generating timestamped segments...")

        segments = []
        if include_timestamps and logits is not None:
            from app.ml.transcription_with_timestamps import TimestampedTranscription

            ts_gen = TimestampedTranscription(
                fps=metadata.get("original_fps", 25), frame_stride=1
            )
            segments = ts_gen.generate_segments(
                logits, character_texts, confidence_scores, min_confidence=0.3
            )

        update_progress(transcription_id, 70, "Refining transcription with NLP...")

        refined_text = raw_text
        refinement_result = None
        try:
            from app.ml.nlp_postprocessing import postprocess_transcription

            refinement_result = postprocess_transcription(
                raw_text,
                confidence_scores=confidence_scores,
                use_grammar=False,
            )
            refined_text = refinement_result["refined"]
            logger.info(f"Refined: '{refined_text}' | changes: {refinement_result['change_count']}")
        except Exception as e:
            logger.warning(f"NLP refinement failed: {e}")

        update_progress(transcription_id, 85, "Saving results...")

        processing_time = time.time() - start_time

        transcription.raw_transcript = raw_text
        transcription.cleaned_transcript = refined_text
        transcription.confidence_score = avg_confidence
        transcription.processing_time_seconds = round(processing_time, 2)
        transcription.model_version = "lip_reading_v1"
        transcription.language_detected = language
        transcription.status = "completed"
        transcription.progress = 100

        if refinement_result:
            if not transcription.details_json:
                transcription.details_json = {}
            transcription.details_json = {
                "nlp_changes": refinement_result["change_count"],
                "confidence_boost": refinement_result["confidence_boost"],
                "preprocessing": {
                    "frames_extracted": metadata.get("extracted_frame_count", 0),
                    "valid_frames": metadata.get("processed_frame_count", 0),
                    "invalid_ratio": metadata.get("invalid_frame_ratio", 0),
                    "detector": metadata.get("detector_type", "unknown"),
                },
                "inference": {
                    "device": inference_result.get("device", "unknown"),
                    "inference_time_ms": inference_result.get("inference_time_ms", 0),
                    "frame_count": inference_result.get("frame_count", 0),
                },
            }

        for seg in segments:
            segment_obj = TranscriptionSegment(
                transcription_id=transcription_id,
                segment_index=seg.get("segment_index", segments.index(seg)),
                start_time_ms=int(seg["start_ms"]),
                end_time_ms=int(seg["end_ms"]),
                text=seg["text"],
                confidence_score=float(seg.get("confidence", avg_confidence)),
            )
            db.add(segment_obj)

        video.status = "processed"
        db.commit()

        update_progress(transcription_id, 100, "Completed!")

        result = {
            "transcription_id": transcription_id,
            "status": "completed",
            "raw_text": raw_text,
            "refined_text": refined_text,
            "confidence": avg_confidence,
            "segments_count": len(segments),
            "processing_time_seconds": round(processing_time, 2),
            "model_version": "lip_reading_v1",
        }

        logger.info(f"Transcription completed: {transcription_id} in {processing_time:.2f}s")
        return result

    except Exception as exc:
        logger.error(f"Transcription failed: {transcription_id} - {str(exc)}", exc_info=True)
        try:
            transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
            if transcription:
                transcription.status = "failed"
                transcription.error_message = str(exc)[:1000]
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.status = "failed"
            db.commit()
        except Exception:
            db.rollback()

        raise self.retry(exc=exc)

    finally:
        db.close()


@celery_app.task
def cleanup_old_videos():
    """Clean up soft-deleted videos older than 30 days."""
    from datetime import datetime, timedelta, timezone

    from app.db.database import SessionLocal
    from app.models.database import Video
    from app.services.storage_service import StorageService

    db = SessionLocal()
    storage = StorageService()

    try:
        threshold = datetime.now(timezone.utc) - timedelta(days=30)
        old_videos = db.query(Video).filter(
            Video.is_deleted == True, Video.updated_at < threshold
        ).all()

        for video in old_videos:
            try:
                storage.delete_video(video.storage_path)
                db.delete(video)
            except Exception as e:
                logger.error(f"Failed to cleanup video {video.id}: {e}")

        db.commit()
        logger.info(f"Cleaned up {len(old_videos)} old videos")
    finally:
        db.close()


@celery_app.task
def warm_up_model():
    """Pre-load model into memory for faster inference."""
    try:
        from app.ml.model_manager import model_manager
        model = model_manager.load_model("lip_reading_v1", device="auto")
        dummy = np.random.rand(75, 224, 224, 3).astype(np.float32)
        model.infer_single_video(dummy, return_confidence=False)
        logger.info("Model warmed up successfully")
    except Exception as e:
        logger.warning(f"Model warm-up failed: {e}")

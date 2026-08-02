"""ML model loading and inference service - integrated with model_manager."""

import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

from app.config import get_settings
from app.core.exceptions import ModelInferenceError

logger = logging.getLogger(__name__)


class ModelService:
    """Service for lip-reading model inference, integrated with model_manager."""

    def __init__(self):
        self.settings = get_settings()
        self._model_manager = None

    @property
    def model_manager(self):
        if self._model_manager is None:
            from app.ml.model_manager import model_manager
            self._model_manager = model_manager
        return self._model_manager

    def load_model(
        self,
        model_name: str = "lip_reading_v1",
        device: Optional[str] = None,
        force_reload: bool = False,
    ) -> Any:
        """Load model via model_manager with caching."""
        device = device or self.settings.MODEL_DEVICE
        return self.model_manager.load_model(
            model_name=model_name,
            device=device,
            force_reload=force_reload,
        )

    def predict(
        self,
        frames: np.ndarray,
        language: str = "en",
        return_confidence: bool = True,
        return_logits: bool = False,
    ) -> Dict[str, Any]:
        """
        Run inference on preprocessed video frames.

        Args:
            frames: Preprocessed frames (T, H, W, C) float32 [0, 1]
            language: Target language code
            return_confidence: Include confidence scores
            return_logits: Include raw logits

        Returns:
            Dict with text, confidence, timing info
        """
        try:
            model = self.model_manager.load_model(
                model_name="lip_reading_v1",
                device=self.settings.MODEL_DEVICE,
            )

            start_time = time.time()

            kwargs = {"return_confidence": return_confidence}
            if return_logits:
                kwargs["return_logits"] = return_logits

            result = model.infer_single_video(frames, **kwargs)

            inference_time = (time.time() - start_time) * 1000

            confidence_scores = result.get("confidence_scores")
            confidence = float(np.mean(confidence_scores)) if confidence_scores else 0.0

            return {
                "raw_transcript": result["text"],
                "characters": result.get("characters", list(result.get("text", ""))),
                "char_indices": result.get("char_indices", []),
                "confidence_score": confidence,
                "confidence_scores": confidence_scores,
                "language": language,
                "inference_time_ms": round(inference_time, 2),
                "device": result.get("device", "unknown"),
                "frame_count": result.get("frame_count", len(frames)),
                "model_type": result.get("model_type", "unknown"),
                "logits": result.get("logits") if return_logits else None,
            }
        except Exception as e:
            raise ModelInferenceError(message=f"Inference failed: {str(e)}", details=str(e))

    def predict_batch(
        self,
        video_frames_list: List[np.ndarray],
        language: str = "en",
    ) -> List[Dict[str, Any]]:
        """Batch inference for multiple videos."""
        try:
            model = self.model_manager.load_model(
                model_name="lip_reading_v1",
                device=self.settings.MODEL_DEVICE,
            )
            results = model.infer_batch(video_frames_list, return_logits=False)
            return [
                {
                    "raw_transcript": r["text"],
                    "confidence_score": float(np.mean(r["confidence_scores"])) if r["confidence_scores"] else 0.0,
                    "language": language,
                }
                for r in results
            ]
        except Exception as e:
            raise ModelInferenceError(message=f"Batch inference failed: {str(e)}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        try:
            model = self.model_manager.get_model("lip_reading_v1", self.settings.MODEL_DEVICE)
            if model:
                return model.get_model_info()
            return {"status": "not_loaded"}
        except Exception:
            return {"status": "error"}

    def unload_model(self):
        """Unload model from memory."""
        self.model_manager.unload_model("lip_reading_v1", self.settings.MODEL_DEVICE)


model_service = ModelService()

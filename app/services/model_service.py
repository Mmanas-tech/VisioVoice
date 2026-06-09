"""ML model loading and inference service."""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from app.config import get_settings
from app.core.exceptions import ModelInferenceError

logger = logging.getLogger(__name__)


class LipReadingModel:
    """Lip-reading model service for inference."""

    def __init__(self):
        self.settings = get_settings()
        self.model = None
        self.device = self.settings.MODEL_DEVICE
        self._loaded = False

    def load_model(self) -> None:
        """Load the lip-reading model from disk."""
        try:
            import torch
            from app.ml.lip_reading_model import LipReadingNetwork

            self.model = LipReadingNetwork(num_classes=500)
            model_path = self.settings.MODEL_PATH

            if os.path.exists(model_path):
                state_dict = torch.load(model_path, map_location=self.device)
                self.model.load_state_dict(state_dict)
                logger.info(f"Model loaded from {model_path}")
            else:
                logger.warning(f"Model file not found at {model_path}, using uninitialized model")

            self.model = self.model.to(self.device)
            self.model.eval()
            self._loaded = True
            logger.info(f"Model loaded on device: {self.device}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise ModelInferenceError(message=f"Model loading failed: {str(e)}")

    def predict(self, frames: np.ndarray, language: str = "en") -> Dict[str, Any]:
        """
        Run inference on preprocessed video frames.

        Args:
            frames: Preprocessed frames array of shape (T, C, H, W)
            language: Target language code

        Returns:
            Dict with transcript, confidence, and timing info
        """
        if not self._loaded:
            self.load_model()

        try:
            import torch

            input_tensor = torch.from_numpy(frames).float().to(self.device)
            if input_tensor.dim() == 4:
                input_tensor = input_tensor.unsqueeze(0)

            with torch.no_grad():
                outputs = self.model(input_tensor)
                probabilities = torch.nn.functional.softmax(outputs, dim=-1)
                confidence, predicted = torch.max(probabilities, dim=-1)

            transcript = self._decode_prediction(predicted.item())
            confidence_score = confidence.item()

            return {
                "raw_transcript": transcript,
                "confidence_score": confidence_score,
                "language": language,
            }
        except Exception as e:
            raise ModelInferenceError(message=f"Inference failed: {str(e)}")

    def _decode_prediction(self, predicted_idx: int) -> str:
        """Decode model prediction index to text."""
        return f"[Model prediction index: {predicted_idx}]"

    def preprocess_frames(self, frames: np.ndarray) -> np.ndarray:
        """Normalize and preprocess frames for model input."""
        normalized = frames.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        normalized = (normalized - mean) / std
        if normalized.ndim == 3:
            normalized = np.transpose(normalized, (2, 0, 1))
        elif normalized.ndim == 4:
            normalized = np.transpose(normalized, (0, 3, 1, 2))
        return normalized

    @property
    def is_loaded(self) -> bool:
        return self._loaded


import os

model_service = LipReadingModel()

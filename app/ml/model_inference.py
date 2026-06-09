"""Production inference pipeline for lip-reading model."""

import contextlib
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn

from app.ml.lip_reading_model import LipReadingModel
from app.ml.vocab import CharacterVocab, DEFAULT_VOCAB

logger = logging.getLogger(__name__)


class LipReadingInference:
    """
    Production inference pipeline for lip-reading.

    Handles model loading, preprocessing, inference, and decoding.
    Optimized for GPU with FP16 mixed precision support.
    """

    def __init__(
        self,
        model_path: str,
        device: str = "auto",
        batch_size: int = 32,
        use_fp16: bool = True,
        vocab: Optional[CharacterVocab] = None,
    ):
        self.device = self._resolve_device(device)
        self.batch_size = batch_size
        self.use_fp16 = use_fp16 and self.device.type == "cuda"
        self.vocab = vocab or DEFAULT_VOCAB

        self.model = self._load_model(model_path)
        self.model.eval()

        if self.use_fp16 and self.device.type == "cuda":
            self.autocast = torch.cuda.amp.autocast()
        else:
            self.autocast = contextlib.nullcontext()

        logger.info(
            f"Inference initialized: device={self.device} | "
            f"fp16={self.use_fp16} | batch_size={batch_size} | "
            f"params={self.model.count_parameters():,}"
        )

    @staticmethod
    def _resolve_device(device: str) -> torch.device:
        if device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(device)

    def _load_model(self, model_path: str) -> LipReadingModel:
        model = LipReadingModel(vocab_size=self.vocab.size)
        try:
            model.load_checkpoint(model_path, strict=False)
            logger.info(f"Model loaded from {model_path}")
        except FileNotFoundError:
            logger.warning(f"Model file not found at {model_path}, using random weights")
        except Exception as e:
            logger.warning(f"Could not load model weights: {e}, using random weights")
        model.to(self.device)
        return model

    @torch.no_grad()
    def infer_single_video(
        self,
        frames: np.ndarray,
        return_confidence: bool = True,
        return_logits: bool = False,
    ) -> Dict[str, Any]:
        """
        Run inference on a single video.

        Args:
            frames: (T, H, W, C) numpy array, float32, range [0, 1]
            return_confidence: Include per-character confidence scores
            return_logits: Include raw logit array

        Returns:
            Dict with text, characters, logits, confidence_scores, inference_time_ms
        """
        start_time = time.time()

        frames_tensor = torch.from_numpy(frames).float().to(self.device)
        if frames_tensor.dim() == 4:
            frames_tensor = frames_tensor.unsqueeze(0)

        with self.autocast:
            logits, attn_weights = self.model(frames_tensor, return_attention=True)

        logits_np = logits.cpu().float().numpy()[0]

        char_indices = np.argmax(logits_np, axis=1)
        character_texts = [self.vocab.idx_to_char.get(int(idx), "?") for idx in char_indices]

        decoded_text = self.vocab.ctc_decode([int(idx) for idx in char_indices])

        confidence_scores = None
        if return_confidence:
            probs = torch.softmax(torch.from_numpy(logits_np), dim=1).numpy()
            confidence_scores = np.max(probs, axis=1).tolist()

        inference_time = (time.time() - start_time) * 1000

        result = {
            "text": decoded_text,
            "characters": character_texts,
            "char_indices": char_indices.tolist(),
            "confidence_scores": confidence_scores,
            "inference_time_ms": round(inference_time, 2),
            "device": str(self.device),
            "frame_count": len(frames),
        }

        if return_logits:
            result["logits"] = logits_np

        if attn_weights is not None:
            result["attention_weights"] = attn_weights.cpu().numpy()[0]

        return result

    def infer_batch(
        self,
        video_frames_list: List[np.ndarray],
        return_logits: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Batch inference for multiple videos.

        Args:
            video_frames_list: List of (T, H, W, C) arrays
            return_logits: Include raw logit arrays

        Returns:
            List of inference results
        """
        results = []
        for i in range(0, len(video_frames_list), self.batch_size):
            batch_frames = video_frames_list[i : i + self.batch_size]
            batch_results = self._infer_batch_internal(batch_frames, return_logits)
            results.extend(batch_results)
        return results

    def _infer_batch_internal(
        self,
        frames_list: List[np.ndarray],
        return_logits: bool,
    ) -> List[Dict[str, Any]]:
        """Internal batch inference with padding."""
        max_len = max(f.shape[0] for f in frames_list)

        padded_frames = []
        original_lengths = []
        for frames in frames_list:
            original_lengths.append(frames.shape[0])
            padding = max_len - frames.shape[0]
            if padding > 0:
                padded = np.pad(frames, ((0, padding), (0, 0), (0, 0), (0, 0)), mode="edge")
            else:
                padded = frames
            padded_frames.append(padded)

        batch_tensor = torch.from_numpy(np.stack(padded_frames)).float().to(self.device)

        with torch.no_grad(), self.autocast:
            logits, _ = self.model(batch_tensor, return_attention=False)

        results = []
        for i, orig_len in enumerate(original_lengths):
            logits_np = logits[i, :orig_len, :].cpu().float().numpy()

            char_indices = np.argmax(logits_np, axis=1)
            character_texts = [self.vocab.idx_to_char.get(int(idx), "?") for idx in char_indices]
            decoded_text = self.vocab.ctc_decode([int(idx) for idx in char_indices])

            probs = torch.softmax(torch.from_numpy(logits_np), dim=1).numpy()
            confidence_scores = np.max(probs, axis=1).tolist()

            result = {
                "text": decoded_text,
                "characters": character_texts,
                "char_indices": char_indices.tolist(),
                "confidence_scores": confidence_scores,
                "device": str(self.device),
                "frame_count": orig_len,
            }
            if return_logits:
                result["logits"] = logits_np
            results.append(result)

        return results

    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata."""
        return {
            "device": str(self.device),
            "use_fp16": self.use_fp16,
            "batch_size": self.batch_size,
            "vocab_size": self.vocab.size,
            "total_parameters": self.model.count_parameters(),
            "model_type": "LipReadingModel-ResNet3D34",
        }

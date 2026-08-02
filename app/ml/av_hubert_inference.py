"""AV-HuBERT inference wrapper for lip-reading.

Wraps Facebook Research's AV-HuBERT model for production inference.
Uses Fairseq framework for checkpoint loading, with custom greedy decoding.

Model: Audio-Visual Hidden Unit BERT (fine-tuned for lip-reading)
Paper: https://arxiv.org/abs/2201.02184
Repo: https://github.com/facebookresearch/av_hubert
"""

import contextlib
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from omegaconf import OmegaConf

logger = logging.getLogger(__name__)

AV_HUBERT_AVAILABLE = False
try:
    import fairseq
    from fairseq import checkpoint_utils, tasks, utils
    from fairseq.dataclass.utils import convert_namespace_to_omegaconf
    AV_HUBERT_AVAILABLE = True
except ImportError:
    logger.warning(
        "Fairseq not installed. AV-HuBERT inference unavailable. "
        "Install with: pip install fairseq"
    )


def _find_av_hubert_user_dir() -> Optional[str]:
    """Find the avhubert package directory for Fairseq user modules."""
    try:
        import avhubert
        return os.path.dirname(avhubert.__file__)
    except ImportError:
        pass

    base = os.path.dirname(os.path.abspath(__file__))
    possible = [
        os.path.join(base, "..", "..", "_av_hubert_ref", "avhubert"),
        os.path.join(base, "..", "_av_hubert_ref", "avhubert"),
        os.path.join(os.getcwd(), "_av_hubert_ref", "avhubert"),
    ]
    for p in possible:
        resolved = os.path.abspath(p)
        if os.path.isdir(resolved):
            return resolved
    return None


class AVHubertPreprocessor:
    """Preprocesses video frames for AV-HuBERT input.

    AV-HuBERT expects:
    - Grayscale frames (1 channel)
    - 88x88 center crop
    - Normalized: (pixel / 255.0 - 0.421) / 0.165
    - Shape: (B, 1, T, 88, 88)
    """

    IMAGE_CROP_SIZE = 88
    IMAGE_MEAN = 0.421
    IMAGE_STD = 0.165

    @staticmethod
    def preprocess_frames(
        frames: np.ndarray,
        device: torch.device,
    ) -> torch.Tensor:
        """
        Convert preprocessed RGB frames to AV-HuBERT format.

        Args:
            frames: (T, H, W, C) float32 [0, 1] RGB frames from VideoPreprocessor
            device: Target torch device

        Returns:
            Tensor of shape (1, 1, T, 88, 88) ready for AV-HuBERT
        """
        if frames.ndim == 4:
            T, H, W, C = frames.shape
        elif frames.ndim == 3:
            T, H, W = frames.shape
            C = 1
        else:
            raise ValueError(f"Expected 3D or 4D array, got {frames.ndim}D")

        if C == 3:
            gray = 0.2989 * frames[:, :, :, 0] + 0.5870 * frames[:, :, :, 1] + 0.1140 * frames[:, :, :, 2]
        else:
            gray = frames[:, :, :, 0] if frames.ndim == 4 else frames

        crop_size = AVHubertPreprocessor.IMAGE_CROP_SIZE
        h, w = gray.shape[1], gray.shape[2]
        if h != crop_size or w != crop_size:
            y_start = max(0, (h - crop_size) // 2)
            x_start = max(0, (w - crop_size) // 2)
            cropped = np.zeros((T, crop_size, crop_size), dtype=np.float32)
            y_end = min(h, y_start + crop_size)
            x_end = min(w, x_start + crop_size)
            cropped[:, :y_end - y_start, :x_end - x_start] = gray[:, y_start:y_end, x_start:x_end]
            gray = cropped

        mean = AVHubertPreprocessor.IMAGE_MEAN
        std = AVHubertPreprocessor.IMAGE_STD
        normalized = (gray / 255.0 - mean) / std if gray.max() > 1.0 else (gray - mean) / std

        tensor = torch.from_numpy(normalized).float()
        tensor = tensor.unsqueeze(0).unsqueeze(0)
        return tensor.to(device)


class AVHubertInference:
    """Production inference pipeline for AV-HuBERT lip-reading.

    Handles model loading, video preprocessing, inference, and text decoding.
    Supports both GPU (FP16/FP32) and CPU inference.
    """

    def __init__(
        self,
        checkpoint_path: str,
        device: str = "auto",
        beam_size: int = 1,
        max_len: int = 256,
        use_fp16: bool = True,
        user_dir: Optional[str] = None,
    ):
        if not AV_HUBERT_AVAILABLE:
            raise ImportError(
                "Fairseq is required for AV-HuBERT inference. "
                "Install with: pip install fairseq"
            )

        self.device = self._resolve_device(device)
        self.beam_size = beam_size
        self.max_len = max_len
        self.use_fp16 = use_fp16 and self.device.type == "cuda"

        self.user_dir = user_dir or _find_av_hubert_user_dir()
        self.model, self.task, self.dictionary = self._load_model(checkpoint_path)

        self.preprocessor = AVHubertPreprocessor()

        logger.info(
            f"AV-HuBERT initialized: device={self.device} | "
            f"fp16={self.use_fp16} | beam={beam_size} | "
            f"vocab_size={len(self.dictionary)}"
        )

    @staticmethod
    def _resolve_device(device: str) -> torch.device:
        if device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(device)

    def _load_model(self, checkpoint_path: str):
        """Load AV-HuBERT model from checkpoint using Fairseq.

        Patches config to point to local dictionary files.
        """
        logger.info(f"Loading AV-HuBERT checkpoint: {checkpoint_path}")

        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(
                f"AV-HuBERT checkpoint not found: {checkpoint_path}. "
                "Download from http://facebookresearch.github.io/av_hubert"
            )

        if self.user_dir:
            user_dir_parent = os.path.dirname(self.user_dir)
            import importlib
            if "avhubert" not in sys.modules:
                sys.path.insert(0, user_dir_parent)
                import avhubert
            else:
                avhubert = sys.modules["avhubert"]

        base_dir = os.path.dirname(os.path.abspath(checkpoint_path))
        pretrain_dict = os.path.join(base_dir, "pretrain_dict")
        s2s_dict = os.path.join(base_dir, "s2s_dict")

        state = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        cfg = state["cfg"]

        cfg["task"]["label_dir"] = s2s_dict
        cfg["task"]["data"] = s2s_dict
        cfg["model"]["w2v_args"]["task"]["label_dir"] = pretrain_dict
        cfg["model"]["w2v_args"]["task"]["data"] = pretrain_dict

        cfg = OmegaConf.create(cfg)
        state["cfg"] = cfg

        models, saved_cfg, task = checkpoint_utils.load_model_ensemble_and_task(
            [checkpoint_path], state=state
        )
        model = models[0]

        if self.use_fp16 and self.device.type == "cuda":
            model.half()
        model.to(self.device)
        model.eval()

        dictionary = task.target_dictionary

        logger.info(
            f"Model loaded: {sum(p.numel() for p in model.parameters()):,} params | "
            f"vocab_size={len(dictionary)}"
        )

        return model, task, dictionary

    @torch.no_grad()
    def infer_single_video(
        self,
        frames: np.ndarray,
        return_confidence: bool = True,
    ) -> Dict[str, Any]:
        """
        Run AV-HuBERT inference on a single video.

        Args:
            frames: (T, H, W, C) numpy array, float32, range [0, 1]
            return_confidence: Include per-token confidence scores

        Returns:
            Dict with text, tokens, confidence_scores, inference_time_ms, etc.
        """
        start_time = time.time()

        video_tensor = self.preprocessor.preprocess_frames(frames, self.device)
        T_video = video_tensor.shape[2]

        source = {"video": video_tensor, "audio": None}
        padding_mask = torch.zeros(
            (1, T_video), dtype=torch.bool, device=self.device
        )

        encoder_out = self.model.encoder(source, padding_mask)

        if self.beam_size > 1:
            decoded_tokens, scores, attentions = self._beam_search_decode(
                encoder_out, padding_mask
            )
        else:
            decoded_tokens, scores, attentions = self._greedy_decode(
                encoder_out, padding_mask
            )

        decoded_text = self._decode_tokens(decoded_tokens)

        confidence_scores = None
        if return_confidence and attentions is not None:
            confidence_scores = self._compute_confidence(attentions)

        inference_time = (time.time() - start_time) * 1000

        return {
            "text": decoded_text,
            "tokens": decoded_tokens.cpu().tolist(),
            "score": float(scores),
            "confidence_scores": confidence_scores,
            "inference_time_ms": round(inference_time, 2),
            "device": str(self.device),
            "frame_count": T_video,
            "model_type": "AV-HuBERT",
        }

    def _greedy_decode(
        self,
        encoder_out: Dict[str, Any],
        padding_mask: torch.Tensor,
    ) -> Tuple[torch.Tensor, float, Optional[torch.Tensor]]:
        """Greedy autoregressive decoding.

        Returns:
            (tokens, score, attention_weights)
        """
        eos = self.dictionary.eos()
        bos = self.dictionary.bos()
        pad = self.dictionary.pad()

        max_len = min(
            self.max_len,
            encoder_out["encoder_out"].size(0) * 2 + 10
        )

        prev_tokens = torch.full((1, 1), bos, dtype=torch.long, device=self.device)
        all_scores = []
        attentions = []

        for step in range(max_len):
            decoder_out = self.model.decoder(
                prev_tokens, encoder_out=encoder_out
            )
            logits = decoder_out[0][:, -1, :]

            attn_weights = None
            if len(decoder_out) > 1 and isinstance(decoder_out[1], dict):
                attn_list = decoder_out[1].get("attn", None)
                if attn_list is not None and len(attn_list) > 0:
                    attn_weights = attn_list[-1]

            next_token_logits = logits[0]
            next_token = next_token_logits.argmax()
            next_score = next_token_logits[next_token].item()

            all_scores.append(next_score)
            if attn_weights is not None:
                attentions.append(attn_weights[0])

            if next_token.item() == eos:
                break

            prev_tokens = torch.cat(
                [prev_tokens, next_token.unsqueeze(0).unsqueeze(0)], dim=1
            )

        if attentions:
            attentions = torch.stack(attentions, dim=0)
        else:
            attentions = None

        tokens = prev_tokens[0, 1:]
        score = sum(all_scores) / len(all_scores) if all_scores else 0.0

        return tokens, score, attentions

    def _beam_search_decode(
        self,
        encoder_out: Dict[str, Any],
        padding_mask: torch.Tensor,
    ) -> Tuple[torch.Tensor, float, Optional[torch.Tensor]]:
        """Beam search decoding.

        Returns:
            (best_tokens, best_score, attention_weights)
        """
        eos = self.dictionary.eos()
        bos = self.dictionary.bos()
        pad = self.dictionary.pad()

        beam_size = self.beam_size
        max_len = min(
            self.max_len,
            encoder_out["encoder_out"].size(0) * 2 + 10
        )

        B_enc = encoder_out["encoder_out"].size(1)
        encoder_out_expanded = {}
        for k, v in encoder_out.items():
            if isinstance(v, torch.Tensor):
                if v.size(1) == B_enc:
                    encoder_out_expanded[k] = v.repeat_interleave(beam_size, dim=1)
                else:
                    encoder_out_expanded[k] = v
            else:
                encoder_out_expanded[k] = v

        beam_scores = torch.zeros(beam_size, device=self.device)
        beam_scores[1:] = float("-inf")

        prev_tokens = torch.full(
            (beam_size, 1), bos, dtype=torch.long, device=self.device
        )

        finished = []
        attentions = None

        for step in range(max_len):
            decoder_out = self.model.decoder(
                prev_tokens, encoder_out=encoder_out_expanded
            )
            logits = decoder_out[0][:, -1, :]

            next_scores = logits + beam_scores.unsqueeze(-1)
            vocab_size = next_scores.size(-1)
            next_scores = next_scores.view(-1, vocab_size)

            topk_scores, topk_tokens = torch.topk(
                next_scores, beam_size, dim=-1
            )

            beam_indices = topk_tokens // vocab_size
            token_indices = topk_tokens % vocab_size

            beam_scores = topk_scores[:, 0]

            prev_tokens_list = []
            for b in range(beam_size):
                parent = beam_indices[b, 0]
                new_token = token_indices[b, 0]
                prev_tokens_list.append(
                    torch.cat([prev_tokens[parent], new_token.unsqueeze(0)])
                )
            prev_tokens = torch.stack(prev_tokens_list)

            for b in range(beam_size):
                if token_indices[b, 0].item() == eos:
                    seq = prev_tokens[b, 1:]
                    seq = seq[seq != pad]
                    finished.append({
                        "tokens": seq,
                        "score": beam_scores[b],
                    })

            if len(finished) >= beam_size:
                break

        if not finished:
            for b in range(beam_size):
                seq = prev_tokens[b, 1:]
                seq = seq[seq != pad]
                finished.append({
                    "tokens": seq,
                    "score": beam_scores[b],
                })

        finished.sort(key=lambda x: x["score"], reverse=True)
        best = finished[0]

        if len(decoder_out) > 1 and isinstance(decoder_out[1], dict):
            attn_list = decoder_out[1].get("attn", None)
            if attn_list is not None and len(attn_list) > 0:
                attentions = attn_list[-1][0:1]

        return best["tokens"], best["score"], attentions

    def _decode_tokens(self, tokens: torch.Tensor) -> str:
        """Decode token IDs to text string."""
        tokens_list = tokens.cpu().tolist()
        symbols_to_ignore = {self.dictionary.eos(), self.dictionary.pad()}
        filtered = [t for t in tokens_list if t not in symbols_to_ignore]
        text = self.dictionary.string(filtered)
        text = text.replace("|", " ").strip()
        text = " ".join(text.split())
        return text

    def _compute_confidence(self, attention: torch.Tensor) -> List[float]:
        """Compute per-token confidence from attention weights."""
        if attention is None:
            return []
        attn = attention.cpu().float()
        if attn.dim() == 3:
            attn = attn.mean(dim=0)
        if attn.dim() == 2:
            confidence = attn.max(dim=-1).values.tolist()
        else:
            confidence = [0.0]
        return confidence

    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata."""
        total_params = sum(p.numel() for p in self.model.parameters())
        return {
            "device": str(self.device),
            "use_fp16": self.use_fp16,
            "beam_size": self.beam_size,
            "vocab_size": len(self.dictionary),
            "total_parameters": total_params,
            "model_type": "AV-HuBERT",
        }


def load_av_hubert(
    checkpoint_path: str,
    device: str = "auto",
    **kwargs,
) -> Optional[AVHubertInference]:
    """Factory function to load AV-HuBERT model.

    Returns None if Fairseq is not available.
    """
    if not AV_HUBERT_AVAILABLE:
        logger.warning("Cannot load AV-HuBERT: Fairseq not installed")
        return None

    try:
        return AVHubertInference(
            checkpoint_path=checkpoint_path,
            device=device,
            **kwargs,
        )
    except Exception as e:
        logger.error(f"Failed to load AV-HuBERT: {e}")
        return None

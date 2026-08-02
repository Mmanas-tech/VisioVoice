"""Singleton model manager for loading and caching lip-reading models.

Supports two backends:
- 'custom': LipReadingModel (ResNet3D-34 + Attention + BiGRU + CTC)
- 'av_hubert': Facebook AV-HuBERT (via Fairseq)

The backend is selected via the MODEL_BACKEND environment variable or
the model_backend parameter in load_model().
"""

import logging
import os
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Singleton manager for loading and caching ML models.

    Prevents reloading the same model multiple times across requests.
    Thread-safe for concurrent Celery workers.

    Supports both custom LipReadingModel and AV-HuBERT backends.
    """

    _instance: Optional["ModelManager"] = None
    _models: Dict[str, Any] = {}

    def __new__(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._models = {}
        return cls._instance

    def load_model(
        self,
        model_name: str = "lip_reading_v1",
        device: str = "auto",
        force_reload: bool = False,
        batch_size: int = 32,
        use_fp16: bool = True,
        vocab=None,
        model_backend: Optional[str] = None,
        **kwargs,
    ):
        """
        Load model with caching.

        Args:
            model_name: Model name (maps to path via config)
            device: "auto", "cuda", "cpu"
            force_reload: Bypass cache and reload
            batch_size: Inference batch size
            use_fp16: Enable mixed precision
            vocab: Custom vocabulary (for custom backend)
            model_backend: "custom" or "av_hubert" (default: auto-detect from env)
            **kwargs: Additional args passed to model constructor

        Returns:
            LipReadingInference or AVHubertInference instance
        """
        if model_backend is None:
            model_backend = os.getenv("MODEL_BACKEND", "auto")

        cache_key = f"{model_name}_{device}_{model_backend}"

        if cache_key in self._models and not force_reload:
            logger.debug(f"Using cached model: {cache_key}")
            return self._models[cache_key]

        if model_backend == "auto":
            model_backend = self._detect_backend(model_name)

        if model_backend == "av_hubert":
            model = self._load_av_hubert(model_name, device, use_fp16, **kwargs)
        else:
            model = self._load_custom(model_name, device, batch_size, use_fp16, vocab)

        self._models[cache_key] = model

        info = model.get_model_info()
        logger.info(
            f"Model loaded: {model_name} ({model_backend}) | "
            f"params={info['total_parameters']:,} | "
            f"device={info['device']}"
        )

        return model

    def _detect_backend(self, model_name: str) -> str:
        """Auto-detect which backend to use."""
        env_backend = os.getenv("MODEL_BACKEND", "")
        if env_backend in ("av_hubert", "custom"):
            return env_backend

        av_hubert_path = os.getenv("AV_HUBERT_CHECKPOINT", "")
        if av_hubert_path and os.path.exists(av_hubert_path):
            return "av_hubert"

        if "av_hubert" in model_name.lower() or "hubert" in model_name.lower():
            return "av_hubert"

        return "custom"

    def _load_av_hubert(
        self,
        model_name: str,
        device: str,
        use_fp16: bool,
        **kwargs,
    ):
        """Load AV-HuBERT model."""
        try:
            from app.ml.av_hubert_inference import AVHubertInference, AV_HUBERT_AVAILABLE
        except ImportError:
            raise ImportError("AV-HuBERT module not found. Ensure app/ml/av_hubert_inference.py exists.")

        if not AV_HUBERT_AVAILABLE:
            raise ImportError(
                "Fairseq is required for AV-HuBERT. "
                "Install with: pip install fairseq"
            )

        checkpoint_path = kwargs.pop("checkpoint_path", None)
        if not checkpoint_path:
            checkpoint_path = os.getenv("AV_HUBERT_CHECKPOINT", "")

        if not checkpoint_path:
            model_dir = os.getenv("MODEL_PATH", "./models")
            checkpoint_path = os.path.join(model_dir, "av_hubert.pt")

        beam_size = kwargs.pop("beam_size", 50)
        len_penalty = kwargs.pop("len_penalty", 1.0)

        return AVHubertInference(
            checkpoint_path=checkpoint_path,
            device=device,
            beam_size=beam_size,
            len_penalty=len_penalty,
            use_fp16=use_fp16,
            **kwargs,
        )

    def _load_custom(
        self,
        model_name: str,
        device: str,
        batch_size: int,
        use_fp16: bool,
        vocab,
    ):
        """Load custom LipReadingModel."""
        from app.ml.model_inference import LipReadingInference
        from app.ml.vocab import CharacterVocab, DEFAULT_VOCAB

        if vocab is None:
            vocab = DEFAULT_VOCAB

        model_path = self._resolve_model_path(model_name)

        logger.info(f"Loading custom model: {model_name} from {model_path}")

        return LipReadingInference(
            model_path=model_path,
            device=device,
            batch_size=batch_size,
            use_fp16=use_fp16,
            vocab=vocab,
        )

    def get_model(
        self,
        model_name: str = "lip_reading_v1",
        device: str = "auto",
        model_backend: Optional[str] = None,
    ):
        """Get a cached model without loading."""
        if model_backend is None:
            model_backend = os.getenv("MODEL_BACKEND", "auto")
        cache_key = f"{model_name}_{device}_{model_backend}"
        return self._models.get(cache_key)

    def unload_model(self, model_name: str, device: str = "auto", model_backend: str = "auto"):
        """Remove model from cache and free memory."""
        cache_key = f"{model_name}_{device}_{model_backend}"
        if cache_key in self._models:
            del self._models[cache_key]
            import gc
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                logger.debug("torch not available for CUDA cache cleanup")
            logger.info(f"Model unloaded: {cache_key}")

    def unload_all(self):
        """Remove all cached models."""
        self._models.clear()
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            logger.debug("torch not available for CUDA cache cleanup")
        logger.info("All models unloaded")

    def get_loaded_models(self) -> Dict[str, Dict[str, Any]]:
        """Get info about all loaded models."""
        result = {}
        for key, model in self._models.items():
            result[key] = model.get_model_info()
        return result

    @staticmethod
    def _resolve_model_path(model_name: str) -> str:
        """Resolve model name to file path."""
        model_dir = os.getenv("MODEL_PATH", "./models")
        path = os.path.join(model_dir, f"{model_name}.pth")
        if not os.path.exists(path):
            alt_path = os.path.join(model_dir, model_name, "model.pth")
            if os.path.exists(alt_path):
                return alt_path
        return path

    @staticmethod
    def get_model_info(model_name: str) -> Dict[str, Any]:
        """Get metadata about a model file."""
        model_dir = os.getenv("MODEL_PATH", "./models")
        path = os.path.join(model_dir, f"{model_name}.pth")
        exists = os.path.exists(path)
        return {
            "name": model_name,
            "path": path,
            "exists": exists,
            "size_mb": round(os.path.getsize(path) / (1024**2), 2) if exists else None,
        }


model_manager = ModelManager()

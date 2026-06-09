"""Singleton model manager for loading and caching lip-reading models."""

import logging
import os
from typing import Any, Dict, Optional

from app.ml.model_inference import LipReadingInference
from app.ml.vocab import CharacterVocab, DEFAULT_VOCAB

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Singleton manager for loading and caching ML models.

    Prevents reloading the same model multiple times across requests.
    Thread-safe for concurrent Celery workers.
    """

    _instance: Optional["ModelManager"] = None
    _models: Dict[str, LipReadingInference] = {}

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
        vocab: Optional[CharacterVocab] = None,
    ) -> LipReadingInference:
        """
        Load model with caching.

        Args:
            model_name: Model name (maps to path via config)
            device: "auto", "cuda", "cpu"
            force_reload: Bypass cache and reload
            batch_size: Inference batch size
            use_fp16: Enable mixed precision
            vocab: Custom vocabulary

        Returns:
            LipReadingInference instance
        """
        cache_key = f"{model_name}_{device}"

        if cache_key in self._models and not force_reload:
            logger.debug(f"Using cached model: {cache_key}")
            return self._models[cache_key]

        model_path = self._resolve_model_path(model_name)

        logger.info(f"Loading model: {model_name} from {model_path}")

        model = LipReadingInference(
            model_path=model_path,
            device=device,
            batch_size=batch_size,
            use_fp16=use_fp16,
            vocab=vocab,
        )

        self._models[cache_key] = model

        info = model.get_model_info()
        logger.info(
            f"Model loaded: {model_name} | "
            f"params={info['total_parameters']:,} | "
            f"device={info['device']}"
        )

        return model

    def get_model(
        self,
        model_name: str = "lip_reading_v1",
        device: str = "auto",
    ) -> Optional[LipReadingInference]:
        """Get a cached model without loading."""
        cache_key = f"{model_name}_{device}"
        return self._models.get(cache_key)

    def unload_model(self, model_name: str, device: str = "auto"):
        """Remove model from cache and free memory."""
        cache_key = f"{model_name}_{device}"
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

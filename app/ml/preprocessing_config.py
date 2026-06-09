"""Preprocessing configuration for the lip-reading pipeline."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PreprocessingConfig:
    """Configuration for video preprocessing and frame extraction."""

    # Frame extraction
    TARGET_FPS: int = 25
    MIN_FRAMES: int = 5
    MAX_FRAMES: int = 5000

    # Mouth region
    MOUTH_WIDTH: int = 224
    MOUTH_HEIGHT: int = 224
    MOUTH_BBOX_PADDING: float = 1.2

    # Normalization
    NORMALIZE_LIGHTING: bool = True
    CLAHE_CLIP_LIMIT: float = 2.0
    CLAHE_TILE_SIZE: tuple = (8, 8)

    # Face detection
    FACE_DETECTOR: str = "mediapipe"
    CONFIDENCE_THRESHOLD: float = 0.5

    # Augmentation (training only)
    AUGMENT_ROTATION: float = 5.0
    AUGMENT_BRIGHTNESS: float = 0.1
    AUGMENT_ZOOM: float = 0.1
    AUGMENT_HORIZONTAL_FLIP: float = 0.5

    # Performance
    NUM_WORKERS: int = 4
    USE_GPU_PREPROCESSING: bool = False
    CACHE_FACE_DETECTIONS: bool = True

    # Memory management
    MEMORY_MAP_THRESHOLD_MB: int = 10240
    CHUNK_SIZE: int = 100

    def validate(self) -> bool:
        """Validate configuration values."""
        if self.TARGET_FPS < 1 or self.TARGET_FPS > 120:
            raise ValueError(f"TARGET_FPS must be between 1 and 120, got {self.TARGET_FPS}")
        if self.MIN_FRAMES < 1:
            raise ValueError(f"MIN_FRAMES must be >= 1, got {self.MIN_FRAMES}")
        if self.MOUTH_WIDTH < 32 or self.MOUTH_HEIGHT < 32:
            raise ValueError("MOUTH dimensions must be >= 32")
        if not 0.0 <= self.CONFIDENCE_THRESHOLD <= 1.0:
            raise ValueError("CONFIDENCE_THRESHOLD must be between 0 and 1")
        return True


@dataclass
class ModelConfig:
    """Configuration for the lip-reading model architecture."""

    # Backbone
    BACKBONE: str = "resnet3d_34"
    PRETRAINED_BACKBONE: bool = True

    # Temporal modeling
    TEMPORAL_KERNEL_SIZE: int = 3
    TEMPORAL_STRIDE: int = 1

    # Attention
    ATTENTION_HEADS: int = 4
    ATTENTION_DIM: int = 128
    ATTENTION_DROPOUT: float = 0.1

    # Decoder
    DECODER_HIDDEN: int = 256
    DECODER_LAYERS: int = 2
    DECODER_DROPOUT: float = 0.3
    DECODER_BIDIRECTIONAL: bool = True

    # Input/Output
    INPUT_FRAMES: int = 75
    INPUT_HEIGHT: int = 224
    INPUT_WIDTH: int = 224
    INPUT_CHANNELS: int = 3
    VOCAB_SIZE: int = 42

    # Training
    BATCH_SIZE: int = 32
    LEARNING_RATE: float = 1e-3
    WEIGHT_DECAY: float = 1e-5
    EPOCHS: int = 100
    PATIENCE: int = 15
    GRAD_CLIP_NORM: float = 1.0

    # Loss
    LOSS_FN: str = "ctc"
    BLANK_INDEX: int = 0

    # Inference
    INFERENCE_BATCH_SIZE: int = 32
    USE_FP16: bool = True
    BEAM_WIDTH: int = 10


@dataclass
class InferenceConfig:
    """Configuration for inference pipeline."""

    MODEL_NAME: str = "lip_reading_v1"
    DEVICE: str = "auto"
    BATCH_SIZE: int = 32
    USE_FP16: bool = True
    MAX_SEQUENCE_LENGTH: int = 5000
    CONFIDENCE_THRESHOLD: float = 0.3
    LANGUAGE: str = "en"
    INCLUDE_TIMESTAMPS: bool = True
    NLP_REFINEMENT: bool = True


DEFAULT_PREPROCESSING_CONFIG = PreprocessingConfig()
DEFAULT_MODEL_CONFIG = ModelConfig()
DEFAULT_INFERENCE_CONFIG = InferenceConfig()

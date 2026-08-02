"""ML model tests."""

import numpy as np
import pytest

from app.ml.lip_reading_model import LipReadingModel
from app.ml.video_preprocessing import (
    augment_frame,
    crop_and_normalize_mouth,
)


class TestLipReadingModel:
    """Test the lip-reading neural network."""

    def test_model_initialization(self):
        model = LipReadingModel(vocab_size=42)
        assert model is not None
        assert model.count_parameters() > 0

    def test_model_forward_pass(self):
        import torch
        model = LipReadingModel(vocab_size=42)
        model.eval()

        dummy_input = torch.randn(1, 3, 10, 224, 224)
        with torch.no_grad():
            logits, _ = model(dummy_input)

        assert logits.dim() == 3
        assert logits.shape[-1] == 42

    def test_model_parameter_count(self):
        model = LipReadingModel(vocab_size=42)
        param_count = sum(p.numel() for p in model.parameters())
        assert param_count > 0

    def test_model_training_mode(self):
        model = LipReadingModel(vocab_size=42)
        model.train()
        assert model.training is True
        model.eval()
        assert model.training is False


class TestVideoPreprocessing:
    """Test video preprocessing utilities."""

    def test_crop_and_normalize(self):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        bbox = (100, 200, 400, 400)
        result = crop_and_normalize_mouth(frame, bbox, target_size=224)
        assert result.shape == (224, 224, 3)
        assert result.dtype == np.float32

    def test_augment_frame(self):
        frame = np.random.rand(224, 224, 3).astype(np.float32)
        rng = np.random.RandomState(42)
        augmented = augment_frame(frame, rng)
        assert augmented.shape == frame.shape
        assert augmented.dtype == np.float32

    def test_augment_frames_deterministic(self):
        frame = np.random.rand(224, 224, 3).astype(np.float32)
        rng1 = np.random.RandomState(42)
        rng2 = np.random.RandomState(42)
        assert np.array_equal(augment_frame(frame, rng1), augment_frame(frame, rng2))


class TestAudioSynthesis:
    """Test audio synthesis utilities."""

    def test_audio_synthesizer_init(self):
        from app.ml.audio.audio_pipeline import AudioSynthesisPipeline
        pipeline = AudioSynthesisPipeline()
        assert pipeline is not None

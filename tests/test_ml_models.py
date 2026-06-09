"""ML model tests."""

import numpy as np
import pytest

from app.ml.lip_reading_model import LipReadingNetwork
from app.ml.video_preprocessing import (
    augment_frames,
    crop_mouth_region,
    extract_frames,
    normalize_frames,
    validate_video,
)


class TestLipReadingNetwork:
    """Test the lip-reading neural network."""

    def test_model_initialization(self):
        model = LipReadingNetwork(num_classes=500)
        assert model is not None
        assert model.classifier is not None

    def test_model_forward_pass(self):
        import torch
        model = LipReadingNetwork(num_classes=100)
        model.eval()

        batch_size = 2
        time_steps = 10
        channels = 3
        height = 224
        width = 224

        dummy_input = torch.randn(batch_size, time_steps, channels, height, width)

        with torch.no_grad():
            output = model(dummy_input)

        assert output.shape == (batch_size * time_steps, 100)

    def test_model_parameter_count(self):
        model = LipReadingNetwork(num_classes=500)
        param_count = sum(p.numel() for p in model.parameters())
        assert param_count > 0

    def test_model_training_mode(self):
        model = LipReadingNetwork(num_classes=500)
        model.train()
        assert model.training is True
        model.eval()
        assert model.training is False


class TestVideoPreprocessing:
    """Test video preprocessing utilities."""

    def test_normalize_frames(self):
        frames = np.random.randint(0, 255, (10, 224, 224, 3), dtype=np.uint8)
        normalized = normalize_frames(frames)
        assert normalized.dtype == np.float32
        assert normalized.min() >= -3.0
        assert normalized.max() <= 3.0

    def test_crop_mouth_region_with_region(self):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        mouth_region = (100, 200, 200, 100)
        cropped = crop_mouth_region(frame, mouth_region)
        assert cropped.shape == (224, 224, 3)

    def test_crop_mouth_region_without_region(self):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        cropped = crop_mouth_region(frame, None)
        assert cropped.shape == (224, 224, 3)

    def test_augment_frames(self):
        frames = np.random.rand(10, 224, 224, 3).astype(np.float32)
        augmented = augment_frames(frames)
        assert augmented.shape == frames.shape
        assert augmented.dtype == np.float32

    def test_augment_frames_deterministic(self):
        frames = np.random.rand(10, 224, 224, 3).astype(np.float32)
        rng = np.random.RandomState(42)
        aug1 = augment_frames(frames, rng)
        rng = np.random.RandomState(42)
        aug2 = augment_frames(frames, rng)
        np.testing.assert_array_equal(aug1, aug2)


class TestAudioSynthesis:
    """Test audio synthesis utilities."""

    def test_audio_synthesizer_init(self):
        from app.ml.audio_synthesis import AudioSynthesizer
        synthesizer = AudioSynthesizer()
        assert synthesizer is not None

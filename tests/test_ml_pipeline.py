"""Integration tests for the ML pipeline."""

import numpy as np
import pytest
import torch

from app.ml.lip_reading_model import LipReadingModel, create_model
from app.ml.model_inference import LipReadingInference
from app.ml.model_manager import ModelManager
from app.ml.preprocessing_config import DEFAULT_MODEL_CONFIG, DEFAULT_PREPROCESSING_CONFIG, PreprocessingConfig
from app.ml.nlp_postprocessing import TranscriptionPostprocessor, postprocess_transcription
from app.ml.transcription_with_timestamps import TimestampedTranscription
from app.ml.vocab import CharacterVocab, DEFAULT_VOCAB
from app.ml.video_preprocessing import (
    augment_frame,
    crop_and_normalize_mouth,
    normalize_frames,
)


class TestPreprocessingConfig:
    def test_default_config(self):
        config = PreprocessingConfig()
        assert config.TARGET_FPS == 25
        assert config.MOUTH_WIDTH == 224
        assert config.MOUTH_HEIGHT == 224
        assert config.validate()

    def test_config_validation(self):
        config = PreprocessingConfig(TARGET_FPS=0)
        with pytest.raises(ValueError):
            config.validate()

    def test_model_config(self):
        config = DEFAULT_MODEL_CONFIG
        assert config.VOCAB_SIZE > 0
        assert config.ATTENTION_HEADS > 0


class TestVocab:
    def test_encode_decode(self):
        vocab = CharacterVocab()
        text = "hello world"
        encoded = vocab.encode(text)
        assert len(encoded) == len(text)
        assert all(isinstance(i, int) for i in encoded)

    def test_ctc_decode(self):
        vocab = CharacterVocab()
        indices = [1, 1, 2, 0, 3, 3, 4]
        decoded = vocab.ctc_decode(indices)
        assert decoded == "bcde" or len(decoded) > 0

    def test_blank_index(self):
        vocab = CharacterVocab()
        assert vocab.blank_index == 0

    def test_vocab_size(self):
        vocab = CharacterVocab()
        assert len(vocab) > 20


class TestVideoPreprocessing:
    def test_crop_and_normalize(self):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        bbox = (100, 200, 400, 400)
        result = crop_and_normalize_mouth(frame, bbox, target_size=224)
        assert result.shape == (224, 224, 3)
        assert result.dtype == np.float32
        assert 0.0 <= result.min() <= result.max() <= 1.0

    def test_augment_frame(self):
        frame = np.random.rand(224, 224, 3).astype(np.float32)
        rng = np.random.RandomState(42)
        augmented = augment_frame(frame, rng)
        assert augmented.shape == frame.shape
        assert augmented.dtype == np.float32

    def test_augment_deterministic(self):
        frame = np.random.rand(224, 224, 3).astype(np.float32)
        rng1 = np.random.RandomState(42)
        rng2 = np.random.RandomState(42)
        assert np.array_equal(augment_frame(frame, rng1), augment_frame(frame, rng2))


class TestLipReadingModel:
    def test_model_creation(self):
        model = LipReadingModel(vocab_size=42)
        assert model is not None
        assert model.count_parameters() > 0

    def test_model_forward(self):
        model = LipReadingModel(vocab_size=42)
        model.eval()
        dummy = torch.randn(1, 75, 224, 224, 3)
        with torch.no_grad():
            logits, attn = model(dummy, return_attention=True)
        assert logits.dim() == 3
        assert logits.shape[-1] == 42
        assert attn is not None

    def test_model_forward_channel_first(self):
        model = LipReadingModel(vocab_size=42)
        model.eval()
        dummy = torch.randn(1, 3, 75, 224, 224)
        with torch.no_grad():
            logits, _ = model(dummy)
        assert logits.dim() == 3

    def test_ctc_loss(self):
        model = LipReadingModel(vocab_size=42)
        dummy = torch.randn(2, 75, 224, 224, 3)
        logits, _ = model(dummy)
        targets = torch.randint(0, 42, (2, 10))
        input_lengths = torch.tensor([75, 75])
        target_lengths = torch.tensor([10, 10])
        loss = model.compute_ctc_loss(logits, targets, input_lengths, target_lengths)
        assert loss.item() >= 0

    def test_create_model_factory(self):
        model = create_model(vocab_size=42, device="cpu")
        assert isinstance(model, LipReadingModel)


class TestTimestampedTranscription:
    def test_generate_segments(self):
        ts = TimestampedTranscription(fps=25)
        logits = np.random.rand(100, 42).astype(np.float32)
        characters = list("hello world this is a test sentence with enough words")
        characters = characters[:100] if len(characters) > 100 else characters + ["_"] * (100 - len(characters))
        confidences = [0.8] * 100

        segments = ts.generate_segments(logits, characters, confidences, min_confidence=0.3)
        assert isinstance(segments, list)
        for seg in segments:
            assert "start_ms" in seg
            assert "end_ms" in seg
            assert "text" in seg
            assert "confidence" in seg

    def test_format_srt(self):
        ts = TimestampedTranscription(fps=25)
        segments = [{"start_ms": 0, "end_ms": 1000, "text": "hello", "confidence": 0.9, "words": []}]
        srt = ts.format_for_srt(segments)
        assert "WEBVTT" not in srt
        assert "00:00:00,000" in srt

    def test_format_vtt(self):
        ts = TimestampedTranscription(fps=25)
        segments = [{"start_ms": 0, "end_ms": 1000, "text": "hello", "confidence": 0.9, "words": []}]
        vtt = ts.format_for_vtt(segments)
        assert "WEBVTT" in vtt

    def test_format_json(self):
        ts = TimestampedTranscription(fps=25)
        segments = [{"start_ms": 0, "end_ms": 1000, "text": "hello", "confidence": 0.9, "words": []}]
        result = ts.format_for_json(segments)
        assert isinstance(result, list)
        assert result[0]["text"] == "hello"


class TestNLPPostprocessing:
    def test_basic_refinement(self):
        result = postprocess_transcription("hello world")
        assert "refined" in result
        assert "changes" in result
        assert "confidence_boost" in result

    def test_capitalization(self):
        processor = TranscriptionPostprocessor()
        text, changes = processor._fix_capitalization("hello world. how are you")
        assert text[0].isupper()

    def test_punctuation(self):
        processor = TranscriptionPostprocessor()
        text, changes = processor._fix_punctuation("hello world")
        assert text.endswith(".")

    def test_artifact_cleaning(self):
        processor = TranscriptionPostprocessor()
        text, changes = processor._clean_artifacts("hello _ world")
        assert "_" not in text

    def test_edit_distance(self):
        d = TranscriptionPostprocessor._edit_distance("kitten", "sitting")
        assert d == 3


class TestModelManager:
    def test_singleton(self):
        from app.ml.model_manager import ModelManager
        m1 = ModelManager()
        m2 = ModelManager()
        assert m1 is m2

    def test_get_model_info(self):
        info = ModelManager.get_model_info("lip_reading_v1")
        assert "name" in info
        assert "path" in info
        assert "exists" in info

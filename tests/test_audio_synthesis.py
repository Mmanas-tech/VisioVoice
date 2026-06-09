"""Integration tests for the audio synthesis pipeline."""

import numpy as np
import pytest

from app.ml.audio.tts_service import TextToSpeechService
from app.ml.audio.audio_enhancement import AudioEnhancementService
from app.ml.audio.lipsync_service import LipSyncAlignmentService
from app.ml.audio.audio_export import AudioExportService
from app.ml.audio.subtitle_service import SubtitleService
from app.ml.audio.voice_cloning import VoiceCloningService
from app.ml.audio.audio_pipeline import AudioSynthesisPipeline, create_audio_pipeline


class TestTTSService:
    def test_init_pyttsx3(self):
        tts = TextToSpeechService(backend="pyttsx3")
        assert tts.sample_rate == 22050

    def test_synthesize_fallback(self):
        tts = TextToSpeechService(backend="nonexistent")
        result = tts.synthesize("Hello world")
        assert "audio" in result
        assert result["duration_seconds"] > 0
        assert result["sample_rate"] == 22050

    def test_synthesize_returns_metadata(self):
        tts = TextToSpeechService(backend="pyttsx3")
        result = tts.synthesize("Test")
        assert "synthesis_time_ms" in result
        assert "backend" in result
        assert "text" in result

    def test_available_backends(self):
        tts = TextToSpeechService(backend="pyttsx3")
        backends = tts.available_backends
        assert isinstance(backends, list)
        assert "fallback" in backends


class TestAudioEnhancement:
    def test_enhance_audio(self):
        service = AudioEnhancementService()
        audio = np.random.randn(22050).astype(np.float32) * 0.5
        result = service.enhance_audio(audio, denoise=True, normalize=True)
        assert "audio" in result
        assert "enhancement_applied" in result
        assert "metrics" in result
        assert len(result["enhancement_applied"]) > 0

    def test_compute_rms(self):
        audio = np.ones(1000) * 0.5
        rms = AudioEnhancementService._compute_rms(audio)
        assert abs(rms - 0.5) < 0.01

    def test_peak_db(self):
        audio = np.ones(1000) * 0.5
        peak = AudioEnhancementService._peak_db(audio)
        assert peak < 0

    def test_normalize_audio(self):
        service = AudioEnhancementService()
        audio = np.random.randn(1000).astype(np.float32) * 0.01
        normalized = service._normalize_audio(audio)
        assert np.max(np.abs(normalized)) <= 1.0

    def test_trim_silence(self):
        service = AudioEnhancementService()
        silence = np.zeros(22050)
        speech = np.random.randn(11025).astype(np.float32) * 0.5
        audio = np.concatenate([silence, speech, silence])
        trimmed = service._trim_silence(audio)
        assert len(trimmed) < len(audio)

    def test_get_audio_stats(self):
        service = AudioEnhancementService()
        audio = np.random.randn(22050).astype(np.float32) * 0.5
        stats = service.get_audio_stats(audio)
        assert "rms" in stats
        assert "peak_db" in stats
        assert "duration_seconds" in stats


class TestLipSyncAlignment:
    def test_align_audio(self):
        service = LipSyncAlignmentService(video_fps=25)
        audio = np.random.randn(22050 * 5).astype(np.float32) * 0.5
        segments = [
            {"start_ms": 0, "end_ms": 2000, "text": "hello"},
            {"start_ms": 2500, "end_ms": 4500, "text": "world"},
        ]
        result = service.align_audio_to_video(audio, 5.0, segments)
        assert "aligned_audio" in result
        assert "confidence" in result
        assert 0 <= result["confidence"] <= 1

    def test_compute_sync_quality(self):
        service = LipSyncAlignmentService()
        audio = np.random.randn(22050 * 5).astype(np.float32)
        quality = service.compute_sync_quality(audio, 5.0)
        assert "duration_match" in quality
        assert 0 <= quality["duration_match"] <= 1


class TestAudioExport:
    def test_export_wav(self, tmp_path):
        service = AudioExportService()
        audio = np.random.randn(22050).astype(np.float32) * 0.5
        output_path = str(tmp_path / "test.wav")
        result = service.export_audio(audio, output_path, format="wav")
        assert result["format"] == "wav"
        assert result["size_mb"] > 0

    def test_supported_formats(self):
        service = AudioExportService()
        formats = service.get_supported_formats()
        assert "wav" in formats
        assert "mp3" in formats

    def test_estimate_file_size(self):
        service = AudioExportService()
        audio = np.random.randn(22050 * 10).astype(np.float32)
        size = service.estimate_file_size(audio, "wav")
        assert size > 0


class TestSubtitleService:
    def test_generate_srt(self):
        service = SubtitleService()
        segments = [
            {"start_ms": 0, "end_ms": 2000, "text": "Hello world"},
            {"start_ms": 2500, "end_ms": 4500, "text": "This is a test"},
        ]
        srt = service.generate_srt(segments)
        assert "00:00:00,000" in srt
        assert "Hello world" in srt

    def test_generate_vtt(self):
        service = SubtitleService()
        segments = [{"start_ms": 0, "end_ms": 1000, "text": "Test"}]
        vtt = service.generate_vtt(segments)
        assert "WEBVTT" in vtt
        assert "00:00:00.000" in vtt

    def test_generate_ass(self):
        service = SubtitleService()
        segments = [{"start_ms": 0, "end_ms": 1000, "text": "Test"}]
        ass = service.generate_ass(segments)
        assert "[Script Info]" in ass
        assert "[V4+ Styles]" in ass

    def test_generate_all_formats(self, tmp_path):
        service = SubtitleService()
        segments = [{"start_ms": 0, "end_ms": 1000, "text": "Test"}]
        paths = service.generate_all_formats(segments, str(tmp_path))
        assert "srt" in paths
        assert "vtt" in paths
        assert "ass" in paths

    def test_wrap_text(self):
        text = "This is a very long sentence that should be wrapped"
        wrapped = SubtitleService._wrap_text(text, 20)
        assert len(wrapped.split("\n")) > 1

    def test_ms_to_srt_timecode(self):
        tc = SubtitleService._ms_to_srt_timecode(3661000)
        assert tc == "01:01:01,000"

    def test_ms_to_vtt_timecode(self):
        tc = SubtitleService._ms_to_vtt_timecode(3661000)
        assert tc == "01:01:01.000"


class TestVoiceCloning:
    def test_init(self):
        service = VoiceCloningService()
        assert service.is_available is False or service.is_available is True

    def test_get_info(self):
        service = VoiceCloningService()
        info = service.get_info()
        assert "available" in info
        assert "device" in info


class TestAudioPipeline:
    def test_create_pipeline(self):
        pipeline = create_audio_pipeline()
        assert isinstance(pipeline, AudioSynthesisPipeline)

    def test_synthesize_from_transcription(self, tmp_path):
        pipeline = create_audio_pipeline(enable_enhancement=False, enable_lipsync=False)
        segments = [
            {"start_ms": 0, "end_ms": 2000, "text": "Hello"},
            {"start_ms": 2500, "end_ms": 4500, "text": "World"},
        ]
        result = pipeline.synthesize_from_transcription(
            transcription_text="Hello World",
            transcription_segments=segments,
            video_duration_seconds=5.0,
            output_dir=str(tmp_path),
            export_formats=["wav"],
            generate_subtitles=True,
        )
        assert "audio_files" in result
        assert "subtitle_files" in result
        assert "metadata" in result

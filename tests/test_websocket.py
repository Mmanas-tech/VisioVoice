"""WebSocket event emitter tests."""

import json
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from app.core.ws_events import (
    _publish_event,
    emit_transcription_progress,
    emit_audio_progress,
    emit_transcription_complete,
    emit_audio_complete,
    emit_error,
)


class TestPublishEvent:
    """Test Redis pub/sub event publishing."""

    @patch("redis.from_url")
    @patch("app.config.get_settings")
    def test_publish_event_success(self, mock_settings, mock_redis):
        mock_settings.return_value.REDIS_URL = "redis://localhost:6379/0"
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        _publish_event("ws:transcription:123", "test_event", {"key": "value"})

        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        assert call_args[0][0] == "ws:transcription:123"
        payload = json.loads(call_args[0][1])
        assert payload["event"] == "test_event"
        assert payload["data"]["key"] == "value"
        mock_client.close.assert_called_once()

    @patch("redis.from_url")
    @patch("app.config.get_settings")
    def test_publish_event_redis_failure(self, mock_settings, mock_redis):
        mock_settings.return_value.REDIS_URL = "redis://localhost:6379/0"
        mock_client = MagicMock()
        mock_client.publish.side_effect = Exception("Connection refused")
        mock_redis.return_value = mock_client

        _publish_event("ws:transcription:123", "test_event", {"key": "value"})

        mock_client.close.assert_not_called()


class TestEmitTranscriptionProgress:
    """Test transcription progress emission."""

    @patch("app.core.ws_events._publish_event")
    def test_emit_progress(self, mock_publish):
        emit_transcription_progress("tx-123", 50, "Processing...")

        mock_publish.assert_called_once_with(
            "ws:transcription:tx-123",
            "transcription_progress",
            {"transcription_id": "tx-123", "progress": 50, "message": "Processing..."},
        )


class TestEmitAudioProgress:
    """Test audio progress emission."""

    @patch("app.core.ws_events._publish_event")
    def test_emit_progress(self, mock_publish):
        emit_audio_progress("tx-123", 75, "Synthesizing audio...")

        mock_publish.assert_called_once_with(
            "ws:transcription:tx-123",
            "audio_progress",
            {"transcription_id": "tx-123", "progress": 75, "message": "Synthesizing audio..."},
        )


class TestEmitTranscriptionComplete:
    """Test transcription completion emission."""

    @patch("app.core.ws_events._publish_event")
    def test_emit_complete(self, mock_publish):
        result = {"raw_transcript": "hello world", "confidence": 0.95}
        emit_transcription_complete("tx-123", result)

        mock_publish.assert_called_once_with(
            "ws:transcription:tx-123",
            "transcription_complete",
            {"transcription_id": "tx-123", "raw_transcript": "hello world", "confidence": 0.95},
        )


class TestEmitAudioComplete:
    """Test audio completion emission."""

    @patch("app.core.ws_events._publish_event")
    def test_emit_complete(self, mock_publish):
        result = {"audio_files": {"wav": "/path/to/audio.wav"}}
        emit_audio_complete("tx-123", result)

        mock_publish.assert_called_once_with(
            "ws:transcription:tx-123",
            "audio_complete",
            {"transcription_id": "tx-123", "audio_files": {"wav": "/path/to/audio.wav"}},
        )


class TestEmitError:
    """Test error emission."""

    @patch("app.core.ws_events._publish_event")
    def test_emit_error(self, mock_publish):
        emit_error("tx-123", "Something went wrong")

        mock_publish.assert_called_once_with(
            "ws:transcription:tx-123",
            "error",
            {"transcription_id": "tx-123", "error": "Something went wrong"},
        )

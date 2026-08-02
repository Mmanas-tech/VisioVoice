"""Integration tests for the API endpoints."""

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.database import User, Video, Transcription, TranscriptionSegment


class TestVideoUploadIntegration:
    """Test video upload flow."""

    def test_upload_video_success(self, client: TestClient, auth_headers: dict):
        video_content = b"fake video content"
        response = client.post(
            "/api/v1/videos/upload",
            files={"file": ("test.mp4", video_content, "video/mp4")},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "uploaded"

    def test_upload_video_no_auth(self, client: TestClient):
        video_content = b"fake video content"
        response = client.post(
            "/api/v1/videos/upload",
            files={"file": ("test.mp4", video_content, "video/mp4")},
        )
        assert response.status_code == 401

    def test_upload_invalid_file_type(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/api/v1/videos/upload",
            files={"file": ("test.txt", b"not a video", "text/plain")},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestTranscriptionIntegration:
    """Test transcription flow."""

    def test_create_transcription_no_video(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/api/v1/transcriptions/process",
            json={"video_id": "nonexistent-id"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_get_transcription_not_found(self, client: TestClient, auth_headers: dict):
        response = client.get(
            "/api/v1/transcriptions/nonexistent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_get_transcription_status_not_found(self, client: TestClient, auth_headers: dict):
        response = client.get(
            "/api/v1/transcriptions/nonexistent-id/status",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_delete_transcription_not_found(self, client: TestClient, auth_headers: dict):
        response = client.delete(
            "/api/v1/transcriptions/nonexistent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestAudioIntegration:
    """Test audio synthesis flow."""

    def test_synthesize_no_transcription(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/api/v1/audio/synthesize/nonexistent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_synthesis_status_not_found(self, client: TestClient, auth_headers: dict):
        response = client.get(
            "/api/v1/audio/synthesize/nonexistent-id/status",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_download_audio_not_found(self, client: TestClient, auth_headers: dict):
        response = client.get(
            "/api/v1/audio/synthesize/nonexistent-id/download/wav",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_list_tts_backends(self, client: TestClient):
        response = client.get("/api/v1/audio/backends")
        assert response.status_code == 200
        data = response.json()
        assert "available_backends" in data
        assert "backends" in data


class TestHealthIntegration:
    """Test health check endpoints."""

    def test_health_check(self, client: TestClient):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data

    def test_readiness_check(self, client: TestClient):
        response = client.get("/api/v1/ready")
        assert response.status_code in (200, 503)

    def test_liveness_check(self, client: TestClient):
        response = client.get("/api/v1/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_metrics(self, client: TestClient):
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200


class TestUserIntegration:
    """Test user endpoints."""

    def test_get_user_not_found(self, client: TestClient, auth_headers: dict):
        response = client.get(
            "/api/v1/users/nonexistent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

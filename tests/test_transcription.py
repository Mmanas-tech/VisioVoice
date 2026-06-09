"""Transcription endpoint tests."""

from fastapi.testclient import TestClient

from app.models.database import User


class TestTranscriptionRequest:
    """Test transcription request endpoint."""

    def test_request_transcription_video_not_found(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/api/v1/transcriptions/process",
            headers=auth_headers,
            json={
                "video_id": "nonexistent-id",
                "language": "en",
                "include_timestamps": True,
                "priority": "normal",
            },
        )
        assert response.status_code == 404

    def test_request_transcription_no_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/transcriptions/process",
            json={"video_id": "test-id"},
        )
        assert response.status_code == 401


class TestTranscriptionGet:
    """Test get transcription endpoint."""

    def test_get_transcription_not_found(self, client: TestClient, auth_headers: dict):
        response = client.get("/api/v1/transcriptions/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404


class TestTranscriptionStatus:
    """Test transcription status endpoint."""

    def test_get_status_not_found(self, client: TestClient, auth_headers: dict):
        response = client.get("/api/v1/transcriptions/nonexistent-id/status", headers=auth_headers)
        assert response.status_code == 404


class TestTranscriptionExport:
    """Test transcription export endpoint."""

    def test_export_not_found(self, client: TestClient, auth_headers: dict):
        response = client.get(
            "/api/v1/transcriptions/nonexistent-id/export?format=json",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_export_invalid_format(self, client: TestClient, auth_headers: dict):
        response = client.get(
            "/api/v1/transcriptions/nonexistent-id/export?format=invalid",
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestTranscriptionDelete:
    """Test transcription deletion endpoint."""

    def test_delete_not_found(self, client: TestClient, auth_headers: dict):
        response = client.delete("/api/v1/transcriptions/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404

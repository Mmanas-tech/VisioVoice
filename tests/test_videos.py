"""Video endpoint tests."""

import io
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.models.database import User


class TestVideoUpload:
    """Test video upload endpoint."""

    def test_upload_video_success(self, client: TestClient, auth_headers: dict):
        video_content = b"fake video content"
        response = client.post(
            "/api/v1/videos/upload",
            headers=auth_headers,
            files={"video_file": ("test.mp4", io.BytesIO(video_content), "video/mp4")},
            data={"title": "Test Video"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.mp4"
        assert data["title"] == "Test Video"
        assert data["status"] == "uploaded"

    def test_upload_video_no_auth(self, client: TestClient):
        response = client.post(
            "/api/v1/videos/upload",
            files={"video_file": ("test.mp4", io.BytesIO(b"content"), "video/mp4")},
        )
        assert response.status_code == 401

    def test_upload_invalid_file_type(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/api/v1/videos/upload",
            headers=auth_headers,
            files={"video_file": ("test.txt", io.BytesIO(b"content"), "text/plain")},
        )
        assert response.status_code == 422


class TestVideoList:
    """Test video listing endpoint."""

    def test_list_videos_empty(self, client: TestClient, auth_headers: dict):
        response = client.get("/api/v1/videos", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_videos_with_pagination(self, client: TestClient, auth_headers: dict):
        response = client.get("/api/v1/videos?page=1&per_page=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["per_page"] == 10


class TestVideoGet:
    """Test get video details endpoint."""

    def test_get_video_not_found(self, client: TestClient, auth_headers: dict):
        response = client.get("/api/v1/videos/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404


class TestVideoDelete:
    """Test video deletion endpoint."""

    def test_delete_video_not_found(self, client: TestClient, auth_headers: dict):
        response = client.delete("/api/v1/videos/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404

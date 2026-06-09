"""Authentication endpoint tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.database import User
from app.core.security import hash_password


class TestAuthRegister:
    """Test user registration endpoint."""

    def test_register_success(self, client: TestClient):
        response = client.post("/api/v1/auth/register", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "NewPass123!",
            "full_name": "New User",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@example.com"
        assert "id" in data

    def test_register_duplicate_email(self, client: TestClient, test_user: User):
        response = client.post("/api/v1/auth/register", json={
            "username": "anotheruser",
            "email": "test@example.com",
            "password": "AnotherPass123!",
        })
        assert response.status_code == 409

    def test_register_duplicate_username(self, client: TestClient, test_user: User):
        response = client.post("/api/v1/auth/register", json={
            "username": "testuser",
            "email": "different@example.com",
            "password": "DifferentPass123!",
        })
        assert response.status_code == 409

    def test_register_weak_password(self, client: TestClient):
        response = client.post("/api/v1/auth/register", json={
            "username": "weakuser",
            "email": "weak@example.com",
            "password": "weak",
        })
        assert response.status_code == 422

    def test_register_invalid_email(self, client: TestClient):
        response = client.post("/api/v1/auth/register", json={
            "username": "invaliduser",
            "email": "not-an-email",
            "password": "InvalidPass123!",
        })
        assert response.status_code == 422


class TestAuthLogin:
    """Test user login endpoint."""

    def test_login_success(self, client: TestClient, test_user: User):
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "TestPass123!",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client: TestClient, test_user: User):
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "WrongPass123!",
        })
        assert response.status_code == 429

    def test_login_nonexistent_user(self, client: TestClient):
        response = client.post("/api/v1/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "SomePass123!",
        })
        assert response.status_code == 429


class TestAuthTokenRefresh:
    """Test token refresh endpoint."""

    def test_refresh_token_success(self, client: TestClient, test_user: User):
        login_response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "TestPass123!",
        })
        refresh_token = login_response.json()["refresh_token"]

        response = client.post("/api/v1/auth/refresh-token", json={
            "refresh_token": refresh_token,
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_refresh_invalid_token(self, client: TestClient):
        response = client.post("/api/v1/auth/refresh-token", json={
            "refresh_token": "invalid.token.here",
        })
        assert response.status_code == 401


class TestAuthMe:
    """Test get current user endpoint."""

    def test_get_me_success(self, client: TestClient, auth_headers: dict):
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    def test_get_me_no_token(self, client: TestClient):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_get_me_invalid_token(self, client: TestClient):
        response = client.get("/api/v1/auth/me", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert response.status_code == 401


class TestAuthLogout:
    """Test logout endpoint."""

    def test_logout_success(self, client: TestClient, auth_headers: dict):
        response = client.post("/api/v1/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"

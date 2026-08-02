"""Rate limiter middleware tests."""

import time
from unittest.mock import MagicMock, patch
import pytest

from app.core.rate_limiter import RateLimitMiddleware


class TestRateLimitMiddleware:
    """Test rate limiting middleware."""

    def _make_middleware(self, requests_per_minute=60, failed_login_limit=5):
        mock_app = MagicMock()
        return RateLimitMiddleware(
            mock_app,
            requests_per_minute=requests_per_minute,
            failed_login_limit=failed_login_limit,
        )

    def _make_request(self, path="/api/v1/videos", method="GET", client_host="127.0.0.1"):
        request = MagicMock()
        request.url.path = path
        request.method = method
        request.client.host = client_host
        request.headers = {}
        return request

    def test_get_client_ip_direct(self):
        middleware = self._make_middleware()
        request = self._make_request()
        ip = middleware._get_client_ip(request)
        assert ip == "127.0.0.1"

    def test_get_client_ip_forwarded(self):
        middleware = self._make_middleware()
        request = self._make_request()
        request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
        ip = middleware._get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_cleanup_old_entries(self):
        middleware = self._make_middleware()
        now = time.time()
        entries = [now - 120, now - 30, now - 10, now]
        cleaned = middleware._cleanup_old_entries(entries, window=60)
        assert len(cleaned) == 3
        assert now in cleaned
        assert now - 10 in cleaned
        assert now - 30 in cleaned

    def test_rate_limit_not_exceeded(self):
        middleware = self._make_middleware(requests_per_minute=10)
        result = middleware._is_rate_limited("test_key", 10, 60)
        assert result is False

    def test_rate_limit_exceeded(self):
        middleware = self._make_middleware(requests_per_minute=2)
        middleware._is_rate_limited("test_key", 2, 60)
        middleware._is_rate_limited("test_key", 2, 60)
        result = middleware._is_rate_limited("test_key", 2, 60)
        assert result is True

    def test_login_rate_limit_not_exceeded(self):
        middleware = self._make_middleware(failed_login_limit=5)
        result = middleware._is_login_rate_limited("192.168.1.1")
        assert result is False

    def test_login_rate_limit_exceeded(self):
        middleware = self._make_middleware(failed_login_limit=3)
        for _ in range(3):
            middleware._record_failed_login("192.168.1.1")
        result = middleware._is_login_rate_limited("192.168.1.1")
        assert result is True

    def test_clear_failed_logins(self):
        middleware = self._make_middleware()
        middleware._record_failed_login("192.168.1.1")
        assert len(middleware._failed_logins["192.168.1.1"]) == 1
        middleware._clear_failed_logins("192.168.1.1")
        assert "192.168.1.1" not in middleware._failed_logins

    def test_rate_limit_window_expiry(self):
        middleware = self._make_middleware(requests_per_minute=2)
        middleware._requests["test_key"] = [time.time() - 120]
        result = middleware._is_rate_limited("test_key", 2, 60)
        assert result is False

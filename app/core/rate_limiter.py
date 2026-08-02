"""Rate limiting middleware."""

import time
import logging
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware."""

    def __init__(self, app, requests_per_minute: int = 60, failed_login_limit: int = 5):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.failed_login_limit = failed_login_limit
        self._requests: Dict[str, list[float]] = defaultdict(list)
        self._failed_logins: Dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup_old_entries(self, entries: list[float], window: int = 60) -> list[float]:
        cutoff = time.time() - window
        return [t for t in entries if t > cutoff]

    def _is_rate_limited(self, key: str, limit: int, window: int = 60) -> bool:
        now = time.time()
        self._requests[key] = self._cleanup_old_entries(self._requests[key], window)
        if len(self._requests[key]) >= limit:
            return True
        self._requests[key].append(now)
        return False

    def _is_login_rate_limited(self, ip: str) -> bool:
        now = time.time()
        self._failed_logins[ip] = self._cleanup_old_entries(self._failed_logins[ip], 300)
        return len(self._failed_logins[ip]) >= self.failed_login_limit

    def _record_failed_login(self, ip: str):
        self._failed_logins[ip].append(time.time())

    def _clear_failed_logins(self, ip: str):
        self._failed_logins.pop(ip, None)

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        settings = get_settings()

        if request.url.path == "/api/v1/auth/login" and request.method == "POST":
            if self._is_login_rate_limited(client_ip):
                logger.warning(f"Rate limit exceeded for login from {client_ip}")
                return Response(
                    content='{"error":"RateLimitExceeded","message":"Too many login attempts. Try again later."}',
                    status_code=429,
                    media_type="application/json",
                )

        rate_key = f"rate:{client_ip}"
        if self._is_rate_limited(rate_key, self.requests_per_minute):
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return Response(
                content='{"error":"RateLimitExceeded","message":"Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
            )

        response = await call_next(request)

        if request.url.path == "/api/v1/auth/login" and request.method == "POST":
            if response.status_code == 200:
                self._clear_failed_logins(client_ip)
            elif response.status_code in (401, 422):
                self._record_failed_login(client_ip)

        return response

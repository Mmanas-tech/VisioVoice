"""Shared API dependencies."""

from typing import Optional
from uuid import uuid4

import redis
from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import decode_token, is_token_blacklisted
from app.db.database import get_sync_db_session
from app.models.database import User


def get_request_id(request: Request) -> str:
    """Extract or generate request ID."""
    return getattr(request.state, "request_id", str(uuid4()))


def get_redis_client() -> redis.Redis:
    """Get Redis client."""
    settings = get_settings()
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_sync_db_session),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> User:
    """Extract and validate current user from JWT token."""
    if not authorization:
        raise AuthenticationError(message="Authorization header required")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError(message="Invalid authorization format")

    token = parts[1]

    if is_token_blacklisted(token, redis_client):
        raise AuthenticationError(message="Token has been revoked")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationError(message="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError(message="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationError(message="User not found")
    if not user.is_active:
        raise AuthenticationError(message="User account is deactivated")

    return user


def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Verify current user is an admin."""
    if not current_user.is_admin:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Admin access required")
    return current_user


def get_optional_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_sync_db_session),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> Optional[User]:
    """Get current user if authenticated, otherwise None."""
    try:
        return get_current_user(authorization, db, redis_client)
    except AuthenticationError:
        return None

"""Authentication endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, RateLimitExceededError
from app.core.security import (
    blacklist_token,
    create_token_pair,
    decode_token,
    hash_password,
    is_token_blacklisted,
    verify_password,
)
from app.db.database import get_sync_db_session
from app.models.database import AuditLog, User
from app.models.schemas import (
    MessageResponse,
    TokenRefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.api.v1.dependencies import get_current_user, get_redis_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


def log_audit(db: Session, user_id: str, action: str, request: Request, **kwargs):
    """Create an audit log entry."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        details_json=kwargs if kwargs else None,
    )
    db.add(log)


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_sync_db_session),
):
    """Register a new user account."""
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise ConflictError(message="Email already registered")

    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise ConflictError(message="Username already taken")

    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(user)
    db.flush()

    log_audit(db, user.id, "register", request)
    db.commit()

    logger.info(f"New user registered: {user.username}")
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_sync_db_session),
    redis_client=Depends(get_redis_client),
):
    """Authenticate user and return tokens."""
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise RateLimitExceededError(message="Invalid email or password")

    if not user.is_active:
        from app.core.exceptions import AuthenticationError
        raise AuthenticationError(message="Account is deactivated")

    tokens = create_token_pair(user.id, user.email, user.is_admin)

    log_audit(db, user.id, "login", request)
    db.commit()

    logger.info(f"User logged in: {user.username}")
    return tokens


@router.post("/refresh-token", response_model=TokenResponse)
def refresh_token(
    body: TokenRefreshRequest,
    db: Session = Depends(get_sync_db_session),
    redis_client=Depends(get_redis_client),
):
    """Refresh access token using refresh token."""
    if is_token_blacklisted(body.refresh_token, redis_client):
        from app.core.exceptions import AuthenticationError
        raise AuthenticationError(message="Refresh token has been revoked")

    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        from app.core.exceptions import AuthenticationError
        raise AuthenticationError(message="Invalid token type")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        from app.core.exceptions import AuthenticationError
        raise AuthenticationError(message="User not found")

    tokens = create_token_pair(user.id, user.email, user.is_admin)

    blacklist_token(body.refresh_token, redis_client)

    return tokens


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db_session),
    redis_client=Depends(get_redis_client),
):
    """Logout and invalidate current token."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split()[1]
        blacklist_token(token, redis_client)

    log_audit(db, current_user.id, "logout", request)
    db.commit()
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return current_user

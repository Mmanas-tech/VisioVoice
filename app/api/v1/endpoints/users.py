"""User management endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_sync_db_session
from app.models.database import User
from app.models.schemas import UserResponse
from app.api.v1.dependencies import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get the current user's profile."""
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_sync_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get a user by ID (admin only or self)."""
    if not current_user.is_admin and current_user.id != user_id:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError(message="Can only view own profile")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(resource="User", resource_id=user_id)
    return user

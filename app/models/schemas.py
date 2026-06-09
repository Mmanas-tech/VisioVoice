"""Pydantic request/response schemas."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """Schema for user registration."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""
    id: str
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str


class VideoUploadResponse(BaseModel):
    """Schema for video upload response."""
    id: str
    filename: str
    original_filename: str
    title: Optional[str]
    size: int
    status: str
    processing_scheduled: bool = False
    created_at: datetime


class VideoResponse(BaseModel):
    """Schema for video response."""
    id: str
    filename: str
    original_filename: str
    title: Optional[str]
    description: Optional[str]
    file_size: int
    duration: Optional[float]
    fps: Optional[float]
    resolution: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    """Schema for paginated video list."""
    items: List[VideoResponse]
    total: int
    page: int
    per_page: int
    pages: int


class TranscriptionRequest(BaseModel):
    """Schema for transcription request."""
    video_id: str
    language: Optional[str] = "en"
    include_timestamps: bool = True
    priority: str = Field("normal", pattern=r"^(normal|high)$")


class TranscriptionResponse(BaseModel):
    """Schema for transcription response."""
    id: str
    video_id: str
    raw_transcript: Optional[str]
    cleaned_transcript: Optional[str]
    confidence_score: Optional[float]
    processing_time_seconds: Optional[float]
    model_version: Optional[str]
    language_detected: Optional[str]
    status: str
    error_message: Optional[str]
    progress: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TranscriptionSegmentResponse(BaseModel):
    """Schema for transcription segment."""
    id: str
    segment_index: int
    start_time_ms: int
    end_time_ms: int
    text: str
    confidence_score: Optional[float]
    speaker_label: Optional[str]

    model_config = {"from_attributes": True}


class TranscriptionDetailResponse(TranscriptionResponse):
    """Schema for detailed transcription with segments."""
    segments: List[TranscriptionSegmentResponse] = []


class TranscriptionJobResponse(BaseModel):
    """Schema for transcription job submission."""
    transcription_id: str
    video_id: str
    status: str
    estimated_processing_time_seconds: Optional[float]
    job_id: Optional[str]


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    timestamp: datetime
    components: dict[str, Any]
    version: str


class PaginatedResponse(BaseModel):
    """Generic paginated response."""
    items: List[Any]
    total: int
    page: int
    per_page: int
    pages: int


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str
    message: str
    details: Optional[Any] = None
    request_id: Optional[str] = None


class MessageResponse(BaseModel):
    """Schema for simple message responses."""
    message: str


class BatchTranscriptionRequest(BaseModel):
    """Schema for batch transcription request."""
    video_ids: List[str]


class BatchTranscriptionResponse(BaseModel):
    """Schema for batch transcription response."""
    jobs: List[TranscriptionJobResponse]

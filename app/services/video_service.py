"""Video processing and validation service."""

import os
from pathlib import Path
from typing import Optional, Tuple

import cv2

from app.config import get_settings
from app.core.exceptions import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    ValidationError,
    VideoProcessingError,
)
from app.services.storage_service import StorageService


class VideoService:
    """Service for video operations and validation."""

    def __init__(self):
        self.settings = get_settings()
        self.storage = StorageService()

    def validate_video_file(self, file_bytes: bytes, filename: str) -> None:
        """Validate uploaded video file type and size."""
        ext = Path(filename).suffix.lower()
        if ext not in self.settings.ALLOWED_VIDEO_TYPES:
            raise UnsupportedFileTypeError(file_type=ext, allowed=self.settings.ALLOWED_VIDEO_TYPES)

        max_size = self.settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_size:
            raise FileTooLargeError(max_size_mb=self.settings.MAX_UPLOAD_SIZE_MB)

    def extract_metadata(self, file_path: str) -> dict:
        """Extract video metadata using OpenCV."""
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                raise VideoProcessingError(message="Cannot open video file")

            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            codec = int(cap.get(cv2.CAP_PROP_FOURCC))

            duration = frame_count / fps if fps > 0 else 0
            codec_str = "".join([chr((codec >> 8 * i) & 0xFF) for i in range(4)])

            cap.release()

            return {
                "duration": round(duration, 2),
                "fps": round(fps, 2),
                "resolution": f"{width}x{height}",
                "codec": codec_str,
                "frame_count": frame_count,
            }
        except Exception as e:
            raise VideoProcessingError(message=f"Failed to extract metadata: {str(e)}")

    def generate_thumbnail(self, file_path: str, output_path: str) -> str:
        """Generate a thumbnail from the first frame."""
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                raise VideoProcessingError(message="Cannot open video for thumbnail")

            ret, frame = cap.read()
            cap.release()

            if not ret:
                raise VideoProcessingError(message="Failed to read first frame")

            height, width = frame.shape[:2]
            target_width = 320
            target_height = int(height * (target_width / width))
            thumbnail = cv2.resize(frame, (target_width, target_height))

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cv2.imwrite(output_path, thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return output_path
        except Exception as e:
            raise VideoProcessingError(message=f"Failed to generate thumbnail: {str(e)}")

    async def save_uploaded_video(
        self,
        file_content: bytes,
        user_id: str,
        filename: str,
        title: Optional[str] = None,
    ) -> dict:
        """Save uploaded video and extract metadata."""
        import io

        file_obj = io.BytesIO(file_content)
        storage_path = self.storage.save_video(file_obj, user_id, filename)

        metadata = self.extract_metadata(storage_path)

        file_size = len(file_content)

        return {
            "storage_path": storage_path,
            "filename": filename,
            "file_size": file_size,
            "title": title or Path(filename).stem,
            **metadata,
        }

"""Storage service abstraction for file management."""

import os
import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional

from app.config import get_settings
from app.core.exceptions import StorageError


class StorageBackend(ABC):
    """Abstract storage backend interface."""

    @abstractmethod
    def save(self, file: BinaryIO, path: str) -> str:
        """Save a file and return the storage path."""
        pass

    @abstractmethod
    def get(self, path: str) -> BinaryIO:
        """Retrieve a file by path."""
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete a file by path."""
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a file exists."""
        pass

    @abstractmethod
    def get_url(self, path: str) -> str:
        """Get a URL or path for accessing the file."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_path: str = "./storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, file: BinaryIO, path: str) -> str:
        full_path = self.base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(full_path, "wb") as f:
                shutil.copyfileobj(file, f)
            return str(full_path)
        except Exception as e:
            raise StorageError(message=f"Failed to save file: {str(e)}")

    def get(self, path: str) -> BinaryIO:
        full_path = self.base_path / path
        if not full_path.exists():
            raise StorageError(message=f"File not found: {path}")
        return open(full_path, "rb")

    def delete(self, path: str) -> bool:
        full_path = self.base_path / path
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def exists(self, path: str) -> bool:
        return (self.base_path / path).exists()

    def get_url(self, path: str) -> str:
        return str(self.base_path / path)


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend."""

    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        try:
            import boto3
            self.client = boto3.client("s3", region_name=region)
        except ImportError:
            raise StorageError(message="boto3 is required for S3 storage")

    def save(self, file: BinaryIO, path: str) -> str:
        try:
            self.client.upload_fileobj(file, self.bucket, path)
            return f"s3://{self.bucket}/{path}"
        except Exception as e:
            raise StorageError(message=f"S3 upload failed: {str(e)}")

    def get(self, path: str) -> BinaryIO:
        import io
        try:
            buffer = io.BytesIO()
            self.client.download_fileobj(self.bucket, path, buffer)
            buffer.seek(0)
            return buffer
        except Exception as e:
            raise StorageError(message=f"S3 download failed: {str(e)}")

    def delete(self, path: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False

    def exists(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False

    def get_url(self, path: str) -> str:
        try:
            return self.client.generate_presigned_url(
                "get_object", Params={"Bucket": self.bucket, "Key": path}, ExpiresIn=3600
            )
        except Exception:
            return f"s3://{self.bucket}/{path}"


class StorageService:
    """Unified storage service interface."""

    def __init__(self):
        settings = get_settings()
        if settings.STORAGE_TYPE == "s3" and settings.AWS_ACCESS_KEY_ID:
            self.backend = S3StorageBackend(
                bucket=settings.AWS_S3_BUCKET, region=settings.AWS_REGION
            )
        else:
            self.backend = LocalStorageBackend(base_path=settings.LOCAL_STORAGE_PATH)

    def save_video(self, file: BinaryIO, user_id: str, filename: str) -> str:
        """Save a video file with user-based path organization."""
        ext = Path(filename).suffix
        unique_name = f"{uuid.uuid4().hex}{ext}"
        path = f"videos/{user_id}/{unique_name}"
        return self.backend.save(file, path)

    def save_thumbnail(self, file: BinaryIO, user_id: str, video_id: str) -> str:
        """Save a thumbnail image."""
        path = f"thumbnails/{user_id}/{video_id}.jpg"
        return self.backend.save(file, path)

    def get_video_path(self, storage_path: str) -> str:
        """Get the full path to a video file."""
        return self.backend.get_url(storage_path)

    def delete_video(self, storage_path: str) -> bool:
        """Delete a video file."""
        return self.backend.delete(storage_path)

    def video_exists(self, storage_path: str) -> bool:
        """Check if a video file exists."""
        return self.backend.exists(storage_path)

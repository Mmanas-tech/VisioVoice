"""Video preprocessing utilities for lip-reading."""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

FRAME_WIDTH = 224
FRAME_HEIGHT = 224
TARGET_FPS = 25
MOUTH_ASPECT_RATIO_THRESHOLD = 0.3


def extract_frames(
    video_path: str,
    target_fps: int = TARGET_FPS,
    target_size: Tuple[int, int] = (FRAME_WIDTH, FRAME_HEIGHT),
) -> np.ndarray:
    """
    Extract frames from video at specified FPS.
    
    Args:
        video_path: Path to video file
        target_fps: Target frames per second
        target_size: Target frame dimensions (width, height)
        
    Returns:
        numpy array of shape (num_frames, height, width, 3)
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if video_fps <= 0:
        raise ValueError(f"Invalid video FPS: {video_fps}")

    frame_interval = max(1, int(video_fps / target_fps))
    logger.info(f"Extracting frames: fps={video_fps}, interval={frame_interval}, total={frame_count}")

    frames = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            resized = cv2.resize(frame, target_size, interpolation=cv2.INTER_LINEAR)
            rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            frames.append(rgb_frame)

        frame_idx += 1

    cap.release()

    if not frames:
        raise ValueError("No frames extracted from video")

    logger.info(f"Extracted {len(frames)} frames")
    return np.array(frames, dtype=np.uint8)


def detect_mouth_region(
    frame: np.ndarray,
    mouth_cascade_path: Optional[str] = None,
) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect mouth region in a single frame.
    
    Args:
        frame: BGR image as numpy array
        path to cascade classifier
        
    Returns:
        Tuple of (x, y, w, h) or None if no mouth detected
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        return None

    x, y, w, h = faces[0]
    face_roi = gray[y:y + h, x:x + w]

    mouth_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_smile.xml")
    mouths = mouth_cascade.detectMultiScale(face_roi, 1.5, 7)

    if len(mouths) > 0:
        mx, my, mw, mh = mouths[0]
        return (x + mx, y + my, mw, mh)

    mouth_y = y + int(h * 0.6)
    mouth_h = int(h * 0.4)
    return (x, mouth_y, w, mouth_h)


def crop_mouth_region(
    frame: np.ndarray,
    mouth_region: Optional[Tuple[int, int, int, int]] = None,
    target_size: Tuple[int, int] = (FRAME_WIDTH, FRAME_HEIGHT),
) -> np.ndarray:
    """
    Crop and resize mouth region from frame.
    
    Args:
        frame: Input frame
        mouth_region: (x, y, w, h) tuple or None for full frame
        target_size: Output size
        
    Returns:
        Cropped and resized frame
    """
    if mouth_region is None:
        return cv2.resize(frame, target_size, interpolation=cv2.INTER_LINEAR)

    x, y, w, h = mouth_region
    h_frame, w_frame = frame.shape[:2]

    x = max(0, min(x, w_frame - 1))
    y = max(0, min(y, h_frame - 1))
    w = min(w, w_frame - x)
    h = min(h, h_frame - y)

    cropped = frame[y:y + h, x:x + w]
    return cv2.resize(cropped, target_size, interpolation=cv2.INTER_LINEAR)


def normalize_frames(frames: np.ndarray) -> np.ndarray:
    """
    Normalize frames for model input.
    
    Args:
        frames: Array of uint8 frames
        
    Returns:
        Normalized float32 frames
    """
    normalized = frames.astype(np.float32) / 255.0

    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    normalized = (normalized - mean) / std

    return normalized


def augment_frames(frames: np.ndarray, random_state: Optional[np.random.RandomState] = None) -> np.ndarray:
    """
    Apply data augmentation to frames.
    
    Args:
        frames: Input frames array
        random_state: Optional random state for reproducibility
        
    Returns:
        Augmented frames
    """
    rng = random_state or np.random.RandomState()
    augmented = frames.copy()

    if rng.random() > 0.5:
        brightness = rng.uniform(0.8, 1.2)
        augmented = np.clip(augmented * brightness, 0, 255)

    if rng.random() > 0.5:
        noise = rng.normal(0, 0.01, augmented.shape).astype(np.float32)
        augmented = np.clip(augmented + noise, 0, 1)

    return augmented


def validate_video(video_path: str) -> dict:
    """
    Validate video file and return metadata.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dictionary with video metadata
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    codec = int(cap.get(cv2.CAP_PROP_FOURCC))

    duration = frame_count / fps if fps > 0 else 0
    codec_str = "".join([chr((codec >> 8 * i) & 0xFF) for i in range(4)])

    cap.release()

    return {
        "fps": round(fps, 2),
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "duration_seconds": round(duration, 2),
        "codec": codec_str,
        "is_valid": fps > 0 and frame_count > 0,
    }

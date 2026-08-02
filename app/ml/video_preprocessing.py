"""Video preprocessing pipeline for lip-reading with face and mouth detection."""

import logging
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.ml.preprocessing_config import PreprocessingConfig, DEFAULT_PREPROCESSING_CONFIG

logger = logging.getLogger(__name__)

FRAME_WIDTH = 224
FRAME_HEIGHT = 224
TARGET_FPS = 25


def extract_frames_from_video(
    video_path: str,
    target_fps: int = TARGET_FPS,
    progress_callback: Optional[callable] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Extract frames from video at specified FPS.

    Args:
        video_path: Path to video file
        target_fps: Target frames per second
        progress_callback: Optional callback(frame_idx, total_frames)

    Returns:
        Tuple of (frames array, metadata dict)

    Raises:
        ValueError: If video cannot be opened or has no frames
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    codec = int(cap.get(cv2.CAP_PROP_FOURCC))

    if video_fps <= 0:
        cap.release()
        raise ValueError(f"Invalid video FPS: {video_fps}")

    duration = frame_count / video_fps
    codec_str = "".join([chr((codec >> 8 * i) & 0xFF) for i in range(4)])
    frame_interval = max(1, int(video_fps / target_fps))

    logger.info(
        f"Extracting frames: {video_path} | "
        f"fps={video_fps:.1f} -> {target_fps} | "
        f"total_frames={frame_count} | interval={frame_interval} | "
        f"duration={duration:.1f}s | resolution={width}x{height}"
    )

    frames = []
    frame_idx = 0
    extracted_count = 0

    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(rgb_frame)
            extracted_count += 1

            if progress_callback and extracted_count % 100 == 0:
                progress_callback(frame_idx, frame_count)

        frame_idx += 1

    cap.release()

    if not frames:
        raise ValueError(f"No frames extracted from video: {video_path}")

    extraction_time = time.time() - start_time
    logger.info(f"Extracted {len(frames)} frames in {extraction_time:.2f}s")

    metadata = {
        "original_fps": video_fps,
        "target_fps": target_fps,
        "original_frame_count": frame_count,
        "extracted_frame_count": len(frames),
        "width": width,
        "height": height,
        "codec": codec_str,
        "duration_seconds": round(duration, 2),
        "frame_interval": frame_interval,
        "extraction_time_seconds": round(extraction_time, 2),
    }

    return np.array(frames, dtype=np.uint8), metadata


def detect_face_landmarks_mediapipe(
    frame: np.ndarray,
    face_mesh: Any,
) -> Optional[Dict[str, Any]]:
    """Detect face landmarks using MediaPipe Face Mesh."""
    h, w = frame.shape[:2]
    input_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) if len(frame.shape) == 3 else frame

    results = face_mesh.process(input_frame)

    if not results.multi_face_landmarks:
        return None

    face_landmarks = results.multi_face_landmarks[0]
    landmarks_px = []
    for lm in face_landmarks.landmark:
        landmarks_px.append([int(lm.x * w), int(lm.y * h)])
    landmarks_px = np.array(landmarks_px)

    mouth_indices = [
        61, 146, 91, 181, 84, 174, 89, 179, 88, 180,
        78, 191, 80, 81, 82, 13, 312, 311, 310, 415,
        308, 324, 318, 402, 317, 14, 87, 178, 88, 95,
    ]
    mouth_points = landmarks_px[mouth_indices]

    x_min, y_min = mouth_points.min(axis=0)
    x_max, y_max = mouth_points.max(axis=0)

    padding = int(max(x_max - x_min, y_max - y_min) * 0.2)
    x_min = max(0, x_min - padding)
    y_min = max(0, y_min - padding)
    x_max = min(w, x_max + padding)
    y_max = min(h, y_max + padding)

    bbox_w = x_max - x_min
    bbox_h = y_max - y_min
    if bbox_w < 32 or bbox_h < 32:
        return None

    return {
        "mouth_bbox": (x_min, y_min, x_max, y_max),
        "landmarks": landmarks_px,
        "mouth_landmarks": mouth_points,
        "confidence": 0.9,
        "is_valid": True,
    }


def detect_face_landmarks_dlib(
    frame: np.ndarray,
    face_detector: Any,
    landmark_predictor: Any,
) -> Optional[Dict[str, Any]]:
    """Detect face landmarks using dlib."""
    import dlib

    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    faces = face_detector(gray, 1)

    if len(faces) == 0:
        return None

    face = max(faces, key=lambda f: (f.right() - f.left()) * (f.bottom() - f.top()))
    landmarks = landmark_predictor(gray, face)
    landmarks_px = np.array([(p.x, p.y) for p in landmarks.parts()])

    mouth_indices = list(range(48, 68))
    mouth_points = landmarks_px[mouth_indices]

    x_min, y_min = mouth_points.min(axis=0)
    x_max, y_max = mouth_points.max(axis=0)

    padding = int(max(x_max - x_min, y_max - y_min) * 0.2)
    x_min = max(0, int(x_min) - padding)
    y_min = max(0, int(y_min) - padding)
    x_max = min(frame.shape[1], int(x_max) + padding)
    y_max = min(frame.shape[0], int(y_max) + padding)

    bbox_w = x_max - x_min
    bbox_h = y_max - y_min
    if bbox_w < 32 or bbox_h < 32:
        return None

    return {
        "mouth_bbox": (x_min, y_min, x_max, y_max),
        "landmarks": landmarks_px,
        "mouth_landmarks": mouth_points,
        "confidence": 0.85,
        "is_valid": True,
    }


def detect_mouth_region(
    frame: np.ndarray,
    face_detector: Any = None,
    detector_type: str = "mediapipe",
) -> Optional[Dict[str, Any]]:
    """
    Detect mouth region in a frame.

    Args:
        frame: RGB frame (H x W x 3)
        face_detector: Detector object (MediaPipe or dlib)
        detector_type: "mediapipe" or "dlib"

    Returns:
        Dict with mouth_bbox, landmarks, confidence, is_valid
    """
    if detector_type == "mediapipe":
        return detect_face_landmarks_mediapipe(frame, face_detector)
    elif detector_type == "dlib":
        return detect_face_landmarks_dlib(frame, face_detector[0], face_detector[1])
    else:
        return _detect_mouth_haar_cascade(frame)


def _detect_mouth_haar_cascade(frame: np.ndarray) -> Optional[Dict[str, Any]]:
    """Fallback mouth detection using Haar cascades."""
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        return None

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])

    mouth_y = y + int(h * 0.6)
    mouth_h = int(h * 0.4)
    mouth_bbox = (x, mouth_y, x + w, mouth_y + mouth_h)

    return {
        "mouth_bbox": mouth_bbox,
        "landmarks": None,
        "mouth_landmarks": None,
        "confidence": 0.6,
        "is_valid": True,
    }


def crop_and_normalize_mouth(
    frame: np.ndarray,
    bbox: Tuple[int, int, int, int],
    target_size: int = FRAME_WIDTH,
    normalize_lighting: bool = True,
    clahe_clip_limit: float = 2.0,
) -> np.ndarray:
    """
    Crop mouth region and normalize.

    Args:
        frame: RGB frame
        bbox: (x1, y1, x2, y2) bounding box
        target_size: Output size (square)
        normalize_lighting: Apply CLAHE
        clahe_clip_limit: CLAHE clip limit

    Returns:
        Normalized mouth region (target_size x target_size x 3) float32 [0, 1]
    """
    x1, y1, x2, y2 = bbox
    h, w = frame.shape[:2]

    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(x1 + 1, min(x2, w))
    y2 = max(y1 + 1, min(y2, h))

    cropped = frame[y1:y2, x1:x2]

    if cropped.size == 0:
        return np.zeros((target_size, target_size, 3), dtype=np.float32)

    aspect = cropped.shape[1] / cropped.shape[0]
    if aspect > 1:
        new_w = target_size
        new_h = int(target_size / aspect)
    else:
        new_h = target_size
        new_w = int(target_size * aspect)

    resized = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    canvas = np.zeros((target_size, target_size, 3), dtype=np.uint8)
    y_offset = (target_size - new_h) // 2
    x_offset = (target_size - new_w) // 2
    canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized

    if normalize_lighting:
        lab = cv2.cvtColor(canvas, cv2.COLOR_RGB2LAB)
        l_channel = lab[:, :, 0]
        clahe = cv2.createCLAHE(clipLimit=clahe_clip_limit, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(l_channel)
        canvas = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    normalized = canvas.astype(np.float32) / 255.0
    return normalized


def augment_frame(
    frame: np.ndarray,
    rng: Optional[np.random.RandomState] = None,
    rotation_deg: float = 5.0,
    brightness_range: float = 0.1,
    zoom_range: float = 0.1,
) -> np.ndarray:
    """Apply data augmentation to a single frame."""
    rng = rng or np.random.RandomState()
    augmented = frame.copy()

    if rng.random() > 0.5:
        angle = rng.uniform(-rotation_deg, rotation_deg)
        h, w = augmented.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        augmented = cv2.warpAffine(augmented, matrix, (w, h), borderMode=cv2.BORDER_REFLECT)

    if rng.random() > 0.5:
        brightness = 1.0 + rng.uniform(-brightness_range, brightness_range)
        augmented = np.clip(augmented * brightness, 0, 1)

    if rng.random() > 0.5:
        zoom = 1.0 + rng.uniform(-zoom_range, zoom_range)
        h, w = augmented.shape[:2]
        new_h, new_w = int(h * zoom), int(w * zoom)
        zoomed = cv2.resize(augmented, (new_w, new_h))
        y_start = max(0, (new_h - h) // 2)
        x_start = max(0, (new_w - w) // 2)
        y_end = min(new_h, y_start + h)
        x_end = min(new_w, x_start + w)
        cropped = np.zeros_like(augmented)
        copy_h = y_end - y_start
        copy_w = x_end - x_start
        cropped[:copy_h, :copy_w] = zoomed[y_start:y_end, x_start:x_end]
        augmented = cropped

    return augmented


class VideoPreprocessor:
    """Complete video preprocessing pipeline for lip-reading."""

    def __init__(self, config: Optional[PreprocessingConfig] = None):
        self.config = config or DEFAULT_PREPROCESSING_CONFIG
        self.config.validate()
        self._face_mesh = None

    def _get_face_mesh(self):
        """Initialize MediaPipe Face Mesh lazily."""
        if self._face_mesh is None:
            try:
                import mediapipe as mp
                self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            except ImportError:
                logger.warning("MediaPipe not available, using Haar cascade fallback")
        return self._face_mesh

    def preprocess_video_for_model(
        self,
        video_path: str,
        augment: bool = False,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Complete preprocessing pipeline.

        Args:
            video_path: Path to video file
            augment: Apply data augmentation
            progress_callback: Progress callback function

        Returns:
            Tuple of (processed frames, metadata)
        """
        start_time = time.time()

        frames, video_metadata = extract_frames_from_video(
            video_path, target_fps=self.config.TARGET_FPS, progress_callback=progress_callback
        )

        face_mesh = self._get_face_mesh()
        detector_type = "mediapipe" if face_mesh else "haar"

        processed_frames = []
        mouth_bboxes = []
        confidence_scores = []
        valid_frames = []
        frame_landmarks = []

        logger.info(f"Processing {len(frames)} frames with {detector_type} detector")

        for i, frame in enumerate(frames):
            detection = detect_mouth_region(frame, face_mesh, detector_type)

            if detection and detection["is_valid"]:
                bbox = detection["mouth_bbox"]
                cropped = crop_and_normalize_mouth(
                    frame, bbox, self.config.MOUTH_WIDTH,
                    self.config.NORMALIZE_LIGHTING, self.config.CLAHE_CLIP_LIMIT,
                )

                if augment:
                    rng = np.random.RandomState(i)
                    cropped = augment_frame(
                        cropped, rng,
                        self.config.AUGMENT_ROTATION,
                        self.config.AUGMENT_BRIGHTNESS,
                        self.config.AUGMENT_ZOOM,
                    )

                processed_frames.append(cropped)
                mouth_bboxes.append(bbox)
                confidence_scores.append(detection["confidence"])
                valid_frames.append(True)
                frame_landmarks.append(detection.get("landmarks"))
            else:
                valid_frames.append(False)
                confidence_scores.append(0.0)
                mouth_bboxes.append(None)
                frame_landmarks.append(None)

            if progress_callback and (i + 1) % 50 == 0:
                progress_callback(i + 1, len(frames))

        invalid_ratio = sum(1 for v in valid_frames if not v) / len(valid_frames)
        if invalid_ratio > 0.3:
            logger.warning(f"High invalid frame ratio: {invalid_ratio:.1%}")

        valid_count = sum(valid_frames)
        if valid_count < self.config.MIN_FRAMES:
            raise ValueError(
                f"Insufficient valid frames: {valid_count} < {self.config.MIN_FRAMES}"
            )

        valid_frame_array = np.array([
            f for f, v in zip(processed_frames, valid_frames) if v
        ])

        total_time = (time.time() - start_time) * 1000

        metadata = {
            **video_metadata,
            "processed_frame_count": len(valid_frame_array),
            "invalid_frame_ratio": round(invalid_ratio, 3),
            "mouth_bboxes": [b for b in mouth_bboxes if b is not None],
            "confidence_scores": [c for c, v in zip(confidence_scores, valid_frames) if v],
            "valid_frames": valid_frames,
            "preprocessing_time_ms": round(total_time, 2),
            "detector_type": detector_type,
        }

        logger.info(
            f"Preprocessing complete: {len(valid_frame_array)} valid frames | "
            f"avg confidence: {np.mean(metadata['confidence_scores']):.3f} | "
            f"time: {total_time:.0f}ms"
        )

        return valid_frame_array, metadata

    def preprocess_video_for_av_hubert(
        self,
        video_path: str,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Preprocess video for AV-HuBERT model.

        AV-HuBERT expects 88x88 grayscale frames normalized with
        mean=0.421, std=0.165. This method returns RGB frames that
        will be converted by AVHubertPreprocessor.

        The preprocessing chain:
        1. Extract frames at 25fps
        2. Detect mouth region (MediaPipe/Haar cascade)
        3. Crop and normalize mouth region
        4. Return RGB float32 frames in [0, 1]

        The AVHubertPreprocessor then converts to grayscale, crops to 88x88,
        and applies AV-HuBERT normalization.

        Args:
            video_path: Path to video file
            progress_callback: Progress callback function

        Returns:
            Tuple of (processed RGB frames, metadata)
        """
        start_time = time.time()

        frames, video_metadata = extract_frames_from_video(
            video_path, target_fps=self.config.TARGET_FPS, progress_callback=progress_callback
        )

        face_mesh = self._get_face_mesh()
        detector_type = "mediapipe" if face_mesh else "haar"

        processed_frames = []
        mouth_bboxes = []
        confidence_scores = []
        valid_frames = []

        for i, frame in enumerate(frames):
            detection = detect_mouth_region(frame, face_mesh, detector_type)

            if detection and detection["is_valid"]:
                bbox = detection["mouth_bbox"]
                cropped = crop_and_normalize_mouth(
                    frame, bbox, self.config.MOUTH_WIDTH,
                    self.config.NORMALIZE_LIGHTING, self.config.CLAHE_CLIP_LIMIT,
                )

                processed_frames.append(cropped)
                mouth_bboxes.append(bbox)
                confidence_scores.append(detection["confidence"])
                valid_frames.append(True)
            else:
                valid_frames.append(False)
                confidence_scores.append(0.0)
                mouth_bboxes.append(None)

            if progress_callback and (i + 1) % 50 == 0:
                progress_callback(i + 1, len(frames))

        valid_count = sum(valid_frames)
        if valid_count < self.config.MIN_FRAMES:
            raise ValueError(
                f"Insufficient valid frames: {valid_count} < {self.config.MIN_FRAMES}"
            )

        valid_frame_array = np.array([
            f for f, v in zip(processed_frames, valid_frames) if v
        ])

        total_time = (time.time() - start_time) * 1000

        metadata = {
            **video_metadata,
            "processed_frame_count": len(valid_frame_array),
            "invalid_frame_ratio": round(
                sum(1 for v in valid_frames if not v) / len(valid_frames), 3
            ),
            "confidence_scores": [c for c, v in zip(confidence_scores, valid_frames) if v],
            "valid_frames": valid_frames,
            "preprocessing_time_ms": round(total_time, 2),
            "detector_type": detector_type,
            "target_model": "av_hubert",
        }

        return valid_frame_array, metadata


def validate_video(video_path: str) -> Dict[str, Any]:
    """Validate video file and return metadata."""
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

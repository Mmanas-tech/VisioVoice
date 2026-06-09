"""Lip-sync alignment service for matching audio to video timing."""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class LipSyncAlignmentService:
    """Align synthesized audio with video frames for synchronization."""

    def __init__(self, video_fps: int = 25):
        self.video_fps = video_fps
        self.frame_duration_ms = 1000.0 / video_fps

    def align_audio_to_video(
        self,
        audio: np.ndarray,
        video_duration_seconds: float,
        transcription_segments: List[Dict],
        sample_rate: int = 22050,
    ) -> Dict[str, Any]:
        """
        Align synthesized audio to match video timing.

        Args:
            audio: Synthesized audio (float32)
            video_duration_seconds: Original video length
            transcription_segments: List of {start_ms, end_ms, text}
            sample_rate: Audio sample rate

        Returns:
            Dict with aligned audio, alignment shifts, sync error, confidence
        """
        audio_duration = len(audio) / sample_rate
        duration_ratio = video_duration_seconds / audio_duration if audio_duration > 0 else 1.0

        aligned_audio = audio
        alignment_shifts = []

        if abs(duration_ratio - 1.0) > 0.05:
            aligned_audio = self._time_stretch(audio, duration_ratio, sample_rate)
            logger.info(f"Time-stretched audio by ratio {duration_ratio:.3f}")

        num_video_frames = int(video_duration_seconds * self.video_fps)
        samples_per_frame = sample_rate / self.video_fps

        for frame_idx in range(min(num_video_frames, 10000)):
            frame_time_ms = frame_idx * self.frame_duration_ms
            matching_seg = self._find_matching_segment(frame_time_ms, transcription_segments)

            if matching_seg:
                expected_sample = int(matching_seg["start_ms"] * sample_rate / 1000)
                actual_sample = int(frame_idx * samples_per_frame)
                shift = actual_sample - expected_sample
                alignment_shifts.append(shift)

        sync_error = float(np.std(alignment_shifts)) if alignment_shifts else 0.0
        confidence = max(0.0, 1.0 - (sync_error / 200.0))

        return {
            "aligned_audio": aligned_audio,
            "alignment_shifts_ms": alignment_shifts[:100],
            "sync_error_ms": round(sync_error, 2),
            "confidence": round(confidence, 4),
            "duration_ratio": round(duration_ratio, 4),
        }

    def compute_segment_alignment(
        self,
        audio: np.ndarray,
        segments: List[Dict],
        sample_rate: int = 22050,
    ) -> List[Dict]:
        """Compute per-segment audio alignment data."""
        aligned_segments = []

        for seg in segments:
            start_sample = int(seg["start_ms"] * sample_rate / 1000)
            end_sample = int(seg["end_ms"] * sample_rate / 1000)
            start_sample = max(0, min(start_sample, len(audio)))
            end_sample = max(start_sample, min(end_sample, len(audio)))

            segment_audio = audio[start_sample:end_sample]

            aligned_segments.append({
                "segment_index": seg.get("segment_index", 0),
                "start_ms": seg["start_ms"],
                "end_ms": seg["end_ms"],
                "text": seg.get("text", ""),
                "audio_start_sample": start_sample,
                "audio_end_sample": end_sample,
                "audio_rms": float(np.sqrt(np.mean(segment_audio ** 2))) if len(segment_audio) > 0 else 0.0,
                "audio_peak_db": float(20 * np.log10(np.max(np.abs(segment_audio)) + 1e-10)) if len(segment_audio) > 0 else -100.0,
            })

        return aligned_segments

    def insert_silence_gaps(
        self,
        audio: np.ndarray,
        segments: List[Dict],
        sample_rate: int = 22050,
    ) -> np.ndarray:
        """Insert silence gaps between segments based on transcription timing."""
        if not segments:
            return audio

        total_duration_ms = segments[-1]["end_ms"] + 500
        total_samples = int(total_duration_ms * sample_rate / 1000)
        output = np.zeros(total_samples, dtype=np.float32)

        for seg in segments:
            start_sample = int(seg["start_ms"] * sample_rate / 1000)
            end_sample = int(seg["end_ms"] * sample_rate / 1000)
            seg_duration = end_sample - start_sample

            src_start = int(seg.get("audio_offset_ms", 0) * sample_rate / 1000)
            src_end = min(src_start + seg_duration, len(audio))
            dst_end = min(start_sample + (src_end - src_start), total_samples)

            seg_len = dst_end - start_sample
            if seg_len > 0 and src_end - src_start >= seg_len:
                output[start_sample:dst_end] = audio[src_start : src_start + seg_len]

        return output

    @staticmethod
    def _time_stretch(audio: np.ndarray, rate: float, sr: int) -> np.ndarray:
        """Stretch audio time without changing pitch."""
        try:
            import librosa
            return librosa.effects.time_stretch(audio, rate=rate)
        except ImportError:
            indices = np.linspace(0, len(audio) - 1, int(len(audio) / rate)).astype(int)
            return audio[indices]

    @staticmethod
    def _find_matching_segment(frame_time_ms: float, segments: List[Dict]) -> Optional[Dict]:
        """Find segment containing given time."""
        for seg in segments:
            if seg["start_ms"] <= frame_time_ms <= seg["end_ms"]:
                return seg
        return None

    def compute_sync_quality(
        self, audio: np.ndarray, video_duration: float, sample_rate: int = 22050
    ) -> Dict[str, float]:
        """Compute synchronization quality metrics."""
        audio_duration = len(audio) / sample_rate
        duration_diff = abs(audio_duration - video_duration)
        duration_match = max(0, 1.0 - (duration_diff / max(video_duration, 0.1)))

        return {
            "duration_match": round(duration_match, 4),
            "audio_duration": round(audio_duration, 3),
            "video_duration": round(video_duration, 3),
            "duration_diff_seconds": round(duration_diff, 3),
        }


lipsync_service = LipSyncAlignmentService()

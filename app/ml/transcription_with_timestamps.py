"""Timestamped transcription generation from model predictions."""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class TimestampedTranscription:
    """Generate timestamped transcription segments from model logits."""

    def __init__(self, fps: int = 25, frame_stride: int = 1):
        self.fps = fps
        self.frame_stride = frame_stride
        self.frame_duration_ms = 1000.0 / fps

    def generate_segments(
        self,
        logits: np.ndarray,
        character_texts: List[str],
        confidence_scores: List[float],
        min_confidence: float = 0.3,
        min_segment_length_ms: float = 100.0,
        merge_gap_ms: float = 150.0,
    ) -> List[Dict[str, Any]]:
        """
        Convert character predictions to timestamped segments.

        Args:
            logits: (T, vocab_size) raw model output
            character_texts: Character predictions per frame
            confidence_scores: Confidence per frame
            min_confidence: Minimum confidence to include a frame
            min_segment_length_ms: Minimum segment duration
            merge_gap_ms: Merge segments closer than this

        Returns:
            List of segment dicts with start_ms, end_ms, text, confidence
        """
        segments = []
        current_segment = None

        for frame_idx, (char, conf) in enumerate(zip(character_texts, confidence_scores)):
            time_ms = frame_idx * self.frame_duration_ms

            if conf < min_confidence or char == "_":
                if current_segment is not None:
                    if current_segment["end_ms"] - current_segment["start_ms"] >= min_segment_length_ms:
                        segments.append(current_segment)
                    current_segment = None
                continue

            if current_segment is None:
                current_segment = {
                    "start_ms": time_ms,
                    "end_ms": time_ms + self.frame_duration_ms,
                    "text": char,
                    "confidence": conf,
                    "frame_indices": [frame_idx],
                    "char_confidences": [conf],
                }
            else:
                time_since_end = time_ms - current_segment["end_ms"]
                if time_since_end > merge_gap_ms:
                    if current_segment["end_ms"] - current_segment["start_ms"] >= min_segment_length_ms:
                        segments.append(current_segment)
                    current_segment = {
                        "start_ms": time_ms,
                        "end_ms": time_ms + self.frame_duration_ms,
                        "text": char,
                        "confidence": conf,
                        "frame_indices": [frame_idx],
                        "char_confidences": [conf],
                    }
                else:
                    current_segment["end_ms"] = time_ms + self.frame_duration_ms
                    current_segment["text"] += char
                    current_segment["frame_indices"].append(frame_idx)
                    current_segment["char_confidences"].append(conf)

        if current_segment is not None:
            if current_segment["end_ms"] - current_segment["start_ms"] >= min_segment_length_ms:
                segments.append(current_segment)

        segments = self._postprocess_segments(segments)
        segments = self._add_words_from_text(segments)

        logger.info(f"Generated {len(segments)} segments")
        return segments

    def _postprocess_segments(self, segments: List[Dict]) -> List[Dict]:
        """Merge close segments and compute average confidence."""
        if not segments:
            return []

        merged = []
        current = segments[0].copy()

        for next_seg in segments[1:]:
            gap_ms = next_seg["start_ms"] - current["end_ms"]

            if gap_ms < 100:
                current["end_ms"] = next_seg["end_ms"]
                current["text"] += next_seg["text"]
                current["frame_indices"].extend(next_seg["frame_indices"])
                current["char_confidences"].extend(next_seg["char_confidences"])
            else:
                current["confidence"] = float(np.mean(current.get("char_confidences", [0.5])))
                if "char_confidences" in current:
                    del current["char_confidences"]
                merged.append(current)
                current = next_seg.copy()

        current["confidence"] = float(np.mean(current.get("char_confidences", [0.5])))
        if "char_confidences" in current:
            del current["char_confidences"]
        merged.append(current)

        return merged

    def _add_words_from_text(self, segments: List[Dict]) -> List[Dict]:
        """Split segment text into words and estimate word-level timestamps."""
        for seg in segments:
            text = seg["text"]
            words = text.split()
            if len(words) <= 1:
                seg["words"] = [{"text": text, "start_ms": seg["start_ms"], "end_ms": seg["end_ms"]}]
                continue

            duration_ms = seg["end_ms"] - seg["start_ms"]
            word_duration = duration_ms / len(words)
            word_list = []
            for i, word in enumerate(words):
                word_start = seg["start_ms"] + i * word_duration
                word_end = word_start + word_duration
                word_list.append({
                    "text": word,
                    "start_ms": round(word_start, 1),
                    "end_ms": round(word_end, 1),
                })
            seg["words"] = word_list

        return segments

    def format_for_srt(self, segments: List[Dict], max_chars_per_line: int = 42) -> str:
        """Format segments as SRT subtitle file."""
        lines = []
        for i, seg in enumerate(segments, 1):
            start_tc = self._ms_to_srt_timecode(seg["start_ms"])
            end_tc = self._ms_to_srt_timecode(seg["end_ms"])
            text = self._wrap_text(seg["text"], max_chars_per_line)
            lines.append(f"{i}\n{start_tc} --> {end_tc}\n{text}\n")
        return "\n".join(lines)

    def format_for_vtt(self, segments: List[Dict]) -> str:
        """Format segments as WebVTT file."""
        lines = ["WEBVTT\n"]
        for seg in segments:
            start_tc = self._ms_to_vtt_timecode(seg["start_ms"])
            end_tc = self._ms_to_vtt_timecode(seg["end_ms"])
            lines.append(f"{start_tc} --> {end_tc}\n{seg['text']}\n")
        return "\n".join(lines)

    def format_for_json(self, segments: List[Dict]) -> List[Dict]:
        """Format segments as clean JSON."""
        return [
            {
                "index": i,
                "start_ms": seg["start_ms"],
                "end_ms": seg["end_ms"],
                "duration_ms": seg["end_ms"] - seg["start_ms"],
                "text": seg["text"],
                "confidence": seg["confidence"],
                "words": seg.get("words", []),
            }
            for i, seg in enumerate(segments)
        ]

    @staticmethod
    def _ms_to_srt_timecode(ms: float) -> str:
        hours = int(ms // 3600000)
        minutes = int((ms % 3600000) // 60000)
        seconds = int((ms % 60000) // 1000)
        millis = int(ms % 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    @staticmethod
    def _ms_to_vtt_timecode(ms: float) -> str:
        hours = int(ms // 3600000)
        minutes = int((ms % 3600000) // 60000)
        seconds = int((ms % 60000) // 1000)
        millis = int(ms % 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"

    @staticmethod
    def _wrap_text(text: str, max_width: int) -> str:
        words = text.split()
        lines = []
        current_line = []
        for word in words:
            test = " ".join(current_line + [word])
            if len(test) <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
        return "\n".join(lines)

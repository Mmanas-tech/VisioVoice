"""Subtitle generation service for SRT, VTT, and ASS formats."""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SubtitleService:
    """Generate subtitle files in SRT, VTT, and ASS formats."""

    def __init__(self, fps: int = 25):
        self.fps = fps
        self.frame_duration_ms = 1000.0 / fps

    def generate_srt(
        self,
        segments: List[Dict],
        output_path: Optional[str] = None,
        max_chars_per_line: int = 42,
    ) -> str:
        """
        Generate SRT subtitle content.

        Format:
        1
        00:00:00,000 --> 00:00:05,000
        Subtitle text here
        """
        srt_lines = []
        for i, seg in enumerate(segments, 1):
            start_tc = self._ms_to_srt_timecode(seg["start_ms"])
            end_tc = self._ms_to_srt_timecode(seg["end_ms"])
            text = self._wrap_text(seg["text"], max_chars_per_line)
            srt_lines.append(f"{i}\n{start_tc} --> {end_tc}\n{text}\n")

        content = "\n".join(srt_lines)

        if output_path:
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"SRT subtitle generated: {output_path}")

        return content

    def generate_vtt(
        self,
        segments: List[Dict],
        output_path: Optional[str] = None,
        max_chars_per_line: int = 42,
    ) -> str:
        """Generate WebVTT subtitle content."""
        vtt_lines = ["WEBVTT\n"]
        for seg in segments:
            start_tc = self._ms_to_vtt_timecode(seg["start_ms"])
            end_tc = self._ms_to_vtt_timecode(seg["end_ms"])
            text = self._wrap_text(seg["text"], max_chars_per_line)
            vtt_lines.append(f"{start_tc} --> {end_tc}\n{text}\n")

        content = "\n".join(vtt_lines)

        if output_path:
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"VTT subtitle generated: {output_path}")

        return content

    def generate_ass(
        self,
        segments: List[Dict],
        output_path: Optional[str] = None,
        style_name: str = "Default",
        font_name: str = "Arial",
        font_size: int = 20,
    ) -> str:
        """Generate Advanced SubStation Alpha (.ass) subtitle content."""
        header = self._generate_ass_header(style_name, font_name, font_size)
        events = []

        for seg in segments:
            start_tc = self._ms_to_ass_timecode(seg["start_ms"])
            end_tc = self._ms_to_ass_timecode(seg["end_ms"])
            text = seg["text"].replace("\n", "\\N")
            events.append(f"Dialogue: 0,{start_tc},{end_tc},{style_name},,0,0,0,,{text}")

        content = header + "\n".join(events) + "\n"

        if output_path:
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"ASS subtitle generated: {output_path}")

        return content

    def generate_all_formats(
        self,
        segments: List[Dict],
        output_dir: str,
        base_name: str = "subtitles",
    ) -> Dict[str, str]:
        """Generate subtitles in all formats and return file paths."""
        os.makedirs(output_dir, exist_ok=True)

        srt_path = os.path.join(output_dir, f"{base_name}.srt")
        vtt_path = os.path.join(output_dir, f"{base_name}.vtt")
        ass_path = os.path.join(output_dir, f"{base_name}.ass")

        self.generate_srt(segments, srt_path)
        self.generate_vtt(segments, vtt_path)
        self.generate_ass(segments, ass_path)

        return {"srt": srt_path, "vtt": vtt_path, "ass": ass_path}

    @staticmethod
    def _generate_ass_header(style_name: str = "Default", font_name: str = "Arial", font_size: int = 20) -> str:
        return f"""[Script Info]
Title: Lip-Reading AI Subtitles
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: {style_name},{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

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
    def _ms_to_ass_timecode(ms: float) -> str:
        hours = int(ms // 3600000)
        minutes = int((ms % 3600000) // 60000)
        seconds = int((ms % 60000) // 1000)
        centiseconds = int((ms % 1000) / 10)
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

    @staticmethod
    def _wrap_text(text: str, max_width: int) -> str:
        words = text.split()
        lines = []
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            if len(test_line) <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
        return "\n".join(lines)


subtitle_service = SubtitleService()

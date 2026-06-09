"""Audio synthesis from transcription text for output generation."""

import logging
import os
import tempfile
from typing import List, Optional

logger = logging.getLogger(__name__)


class AudioSynthesizer:
    """Text-to-speech synthesis for transcription output."""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        """Initialize TTS engine lazily."""
        if self._engine is None:
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", 150)
                self._engine.setProperty("volume", 1.0)
            except (ImportError, RuntimeError):
                logger.warning("pyttsx3 not available, TTS disabled")
                return None
        return self._engine

    def synthesize(
        self,
        text: str,
        output_path: Optional[str] = None,
        voice_rate: int = 150,
        voice_volume: float = 1.0,
    ) -> str:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            voice_rate: Speech rate (words per minute)
            voice_volume: Volume level (0.0 to 1.0)

        Returns:
            Path to the generated audio file
        """
        engine = self._get_engine()
        if engine is None:
            raise RuntimeError("TTS engine not available")

        engine.setProperty("rate", voice_rate)
        engine.setProperty("volume", voice_volume)

        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        engine.save_to_file(text, output_path)
        engine.runAndWait()

        logger.info(f"Audio synthesized: {output_path}")
        return output_path

    def synthesize_segments(
        self,
        segments: List[dict],
        output_dir: str,
        voice_rate: int = 150,
    ) -> List[str]:
        """
        Synthesize audio for multiple transcription segments.

        Args:
            segments: List of segment dicts with 'text' and timing info
            output_dir: Directory to save audio files
            voice_rate: Speech rate

        Returns:
            List of paths to generated audio files
        """
        os.makedirs(output_dir, exist_ok=True)
        audio_files = []

        for i, segment in enumerate(segments):
            text = segment.get("text", "")
            if not text.strip():
                continue

            output_path = os.path.join(output_dir, f"segment_{i:04d}.wav")
            try:
                self.synthesize(text, output_path, voice_rate)
                audio_files.append(output_path)
            except Exception as e:
                logger.error(f"Failed to synthesize segment {i}: {e}")

        return audio_files

    @staticmethod
    def combine_audio_files(audio_files: List[str], output_path: str) -> str:
        """
        Combine multiple audio files into one.

        Args:
            audio_files: List of audio file paths
            output_path: Output file path

        Returns:
            Path to combined audio file
        """
        try:
            from pydub import AudioSegment

            combined = AudioSegment.empty()
            for file_path in audio_files:
                if os.path.exists(file_path):
                    segment = AudioSegment.from_wav(file_path)
                    combined += segment

            combined.export(output_path, format="wav")
            logger.info(f"Combined audio saved: {output_path}")
            return output_path
        except ImportError:
            logger.warning("pydub not available, cannot combine audio")
            return audio_files[0] if audio_files else ""


audio_synthesizer = AudioSynthesizer()

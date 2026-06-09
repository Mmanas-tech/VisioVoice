"""Audio export service for multiple output formats."""

import logging
import os
import subprocess
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class AudioExportService:
    """Export audio in various formats with metadata."""

    def __init__(self, sample_rate: int = 22050):
        self.sr = sample_rate

    def export_audio(
        self,
        audio: np.ndarray,
        output_path: str,
        format: str = "wav",
        metadata: Optional[Dict[str, str]] = None,
        bitrate: str = "192k",
    ) -> Dict[str, Any]:
        """
        Export audio to file.

        Args:
            audio: Waveform (float32, range [-1, 1])
            output_path: Output file path
            format: "wav", "mp3", "aac", "flac", "ogg"
            metadata: ID3 tags
            bitrate: For lossy formats

        Returns:
            Dict with path, size, duration, format info
        """
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        audio_clipped = np.clip(audio, -0.99, 0.99)

        if format == "wav":
            self._export_wav(audio_clipped, output_path)
        elif format == "mp3":
            self._export_mp3(audio_clipped, output_path, bitrate)
        elif format == "flac":
            self._export_flac(audio_clipped, output_path)
        elif format == "aac":
            self._export_aac(audio_clipped, output_path, bitrate)
        elif format == "ogg":
            self._export_ogg(audio_clipped, output_path, bitrate)
        else:
            self._export_wav(audio_clipped, output_path)
            format = "wav"

        file_size_mb = os.path.getsize(output_path) / (1024 ** 2) if os.path.exists(output_path) else 0
        duration = len(audio) / self.sr

        if metadata and format in ("mp3", "flac"):
            self._add_metadata_ffmpeg(output_path, metadata)

        logger.info(f"Audio exported: {output_path} ({file_size_mb:.2f} MB, {format})")

        return {
            "path": output_path,
            "size_mb": round(file_size_mb, 4),
            "duration_seconds": round(duration, 3),
            "format": format,
            "sample_rate": self.sr,
            "channels": 1,
            "bitrate": bitrate,
        }

    def _export_wav(self, audio: np.ndarray, path: str):
        """Export as WAV file."""
        try:
            import soundfile as sf
            sf.write(path, audio, self.sr, subtype="PCM_16")
        except ImportError:
            import wave
            with wave.open(path, "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sr)
                audio_int16 = (audio * 32767).astype(np.int16)
                wf.writeframes(audio_int16.tobytes())

    def _export_mp3(self, audio: np.ndarray, path: str, bitrate: str = "192k"):
        """Export as MP3 via ffmpeg."""
        temp_wav = path.replace(".mp3", "_temp.wav")
        self._export_wav(audio, temp_wav)
        try:
            subprocess.run(
                ["ffmpeg", "-i", temp_wav, "-b:a", bitrate, "-y", path],
                check=True, capture_output=True, timeout=30,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ffmpeg not available for MP3, saving as WAV")
            os.rename(temp_wav, path.replace(".mp3", ".wav"))
            return
        finally:
            if os.path.exists(temp_wav):
                os.remove(temp_wav)

    def _export_flac(self, audio: np.ndarray, path: str):
        """Export as FLAC file."""
        try:
            import soundfile as sf
            sf.write(path, audio, self.sr, subtype="PCM_24")
        except ImportError:
            self._export_wav(audio, path.replace(".flac", ".wav"))

    def _export_aac(self, audio: np.ndarray, path: str, bitrate: str = "192k"):
        """Export as AAC via ffmpeg."""
        temp_wav = path.replace(".aac", "_temp.wav")
        self._export_wav(audio, temp_wav)
        try:
            subprocess.run(
                ["ffmpeg", "-i", temp_wav, "-c:a", "aac", "-b:a", bitrate, "-y", path],
                check=True, capture_output=True, timeout=30,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ffmpeg not available for AAC")
        finally:
            if os.path.exists(temp_wav):
                os.remove(temp_wav)

    def _export_ogg(self, audio: np.ndarray, path: str, bitrate: str = "192k"):
        """Export as OGG via ffmpeg."""
        temp_wav = path.replace(".ogg", "_temp.wav")
        self._export_wav(audio, temp_wav)
        try:
            subprocess.run(
                ["ffmpeg", "-i", temp_wav, "-c:a", "libvorbis", "-b:a", bitrate, "-y", path],
                check=True, capture_output=True, timeout=30,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ffmpeg not available for OGG")
        finally:
            if os.path.exists(temp_wav):
                os.remove(temp_wav)

    def _add_metadata_ffmpeg(self, file_path: str, metadata: Dict[str, str]):
        """Add metadata tags via ffmpeg."""
        temp_path = file_path + ".tmp"
        try:
            cmd = ["ffmpeg", "-i", file_path]
            for key, value in metadata.items():
                cmd.extend(["-metadata", f"{key}={value}"])
            cmd.extend(["-c", "copy", "-y", temp_path])
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            os.replace(temp_path, file_path)
        except (subprocess.CalledProcessError, FileNotFoundError):
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def get_supported_formats(self) -> list:
        """List supported export formats."""
        return ["wav", "mp3", "flac", "aac", "ogg"]

    def estimate_file_size(self, audio: np.ndarray, format: str, bitrate: str = "192k") -> float:
        """Estimate output file size in MB."""
        duration = len(audio) / self.sr
        if format == "wav":
            return duration * self.sr * 2 / (1024 ** 2)
        elif format == "flac":
            return duration * self.sr * 3 / (1024 ** 2) * 0.6
        else:
            try:
                bitrate_kbps = int(bitrate.replace("k", ""))
            except ValueError:
                bitrate_kbps = 192
            return duration * bitrate_kbps * 1000 / (8 * 1024 ** 2)


audio_export = AudioExportService()

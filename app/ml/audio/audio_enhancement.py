"""Audio enhancement and noise reduction service."""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class AudioEnhancementService:
    """Post-process synthesized audio for quality improvement."""

    def __init__(self, sample_rate: int = 22050):
        self.sr = sample_rate

    def enhance_audio(
        self,
        audio: np.ndarray,
        denoise: bool = True,
        normalize: bool = True,
        remove_silence: bool = False,
        equalize: bool = True,
        compress: bool = False,
    ) -> Dict[str, Any]:
        """
        Complete audio enhancement pipeline.

        Args:
            audio: Input waveform (float32, range [-1, 1])
            denoise: Apply noise reduction
            normalize: Normalize amplitude
            remove_silence: Remove leading/trailing silence
            equalize: Apply EQ for brightness
            compress: Apply dynamic range compression

        Returns:
            Dict with enhanced audio, applied enhancements, and metrics
        """
        original_audio = audio.copy()
        metrics = {"rms_before": self._compute_rms(audio), "peak_before_db": self._peak_db(audio)}
        enhancements = []

        if denoise:
            audio = self._denoise_spectral_subtraction(audio)
            enhancements.append("spectral_subtraction")

        if normalize:
            audio = self._normalize_audio(audio)
            enhancements.append("normalization")

        if remove_silence:
            audio = self._trim_silence(audio)
            enhancements.append("silence_removal")

        if equalize:
            audio = self._apply_eq(audio)
            enhancements.append("equalization")

        if compress:
            audio = self._apply_compression(audio)
            enhancements.append("compression")

        audio = np.clip(audio, -1.0, 1.0)

        metrics["rms_after"] = self._compute_rms(audio)
        metrics["peak_after_db"] = self._peak_db(audio)
        metrics["loudness_change_db"] = 20 * np.log10(metrics["rms_after"] / max(metrics["rms_before"], 1e-10))

        logger.info(f"Audio enhancement: {len(enhancements)} effects applied")

        return {
            "audio": audio,
            "enhancement_applied": enhancements,
            "metrics": metrics,
        }

    def _denoise_spectral_subtraction(
        self, audio: np.ndarray, noise_factor: float = 0.8, noise_duration_s: float = 0.5
    ) -> np.ndarray:
        """Spectral subtraction noise reduction using noise profile from first N seconds."""
        try:
            import scipy.fft as fft

            noise_samples = min(int(noise_duration_s * self.sr), len(audio) // 4)
            if noise_samples < 256:
                return audio

            noise_profile = audio[:noise_samples]
            noise_fft = np.abs(fft.fft(noise_profile))
            noise_power = np.mean(noise_fft ** 2)

            frame_size = 2048
            hop_size = frame_size // 4
            enhanced = np.zeros_like(audio)

            for i in range(0, len(audio) - frame_size, hop_size):
                frame = audio[i : i + frame_size]
                window = np.hanning(frame_size)
                windowed = frame * window

                frame_fft = fft.fft(windowed)
                frame_mag = np.abs(frame_fft)
                frame_phase = np.angle(frame_fft)

                denoised_mag = frame_mag - noise_factor * np.sqrt(noise_power)
                denoised_mag = np.maximum(denoised_mag, 0.1 * frame_mag)

                denoised_fft = denoised_mag * np.exp(1j * frame_phase)
                denoised_frame = np.real(fft.ifft(denoised_fft))
                enhanced[i : i + frame_size] += denoised_frame * window

            max_val = np.max(np.abs(enhanced))
            if max_val > 0:
                enhanced = enhanced / max_val

            return enhanced
        except ImportError:
            logger.warning("scipy not available for spectral subtraction")
            return audio

    def _normalize_audio(self, audio: np.ndarray, target_db: float = -20.0) -> np.ndarray:
        """Normalize audio to target loudness level."""
        rms = self._compute_rms(audio)
        if rms < 1e-10:
            return audio

        current_db = 20 * np.log10(rms)
        gain_db = target_db - current_db
        gain = 10 ** (gain_db / 20)

        normalized = audio * gain
        return np.clip(normalized, -1.0, 1.0)

    def _trim_silence(self, audio: np.ndarray, threshold_db: float = -40.0) -> np.ndarray:
        """Remove leading and trailing silence."""
        threshold = 10 ** (threshold_db / 20)
        non_silent = np.abs(audio) > threshold

        if not np.any(non_silent):
            return audio

        start = np.argmax(non_silent)
        end = len(audio) - np.argmax(non_silent[::-1])

        pad = int(0.05 * self.sr)
        start = max(0, start - pad)
        end = min(len(audio), end + pad)

        return audio[start:end]

    def _apply_eq(
        self,
        audio: np.ndarray,
        bass_boost_db: float = 2.0,
        presence_db: float = 1.5,
        treble_boost_db: float = 2.0,
    ) -> np.ndarray:
        """Apply 3-band parametric EQ for brightness."""
        try:
            from scipy.signal import butter, filtfilt

            result = audio.copy()

            b_bass, a_bass = butter(2, 200 / (self.sr / 2), btype="low")
            bass = filtfilt(b_bass, a_bass, audio)
            result += bass * (10 ** (bass_boost_db / 20) - 1)

            b_mid, a_mid = butter(2, [1000 / (self.sr / 2), 4000 / (self.sr / 2)], btype="band")
            mid = filtfilt(b_mid, a_mid, audio)
            result += mid * (10 ** (presence_db / 20) - 1)

            b_treble, a_treble = butter(2, 6000 / (self.sr / 2), btype="high")
            treble = filtfilt(b_treble, a_treble, audio)
            result += treble * (10 ** (treble_boost_db / 20) - 1)

            return np.clip(result, -1.0, 1.0)
        except ImportError:
            return audio

    def _apply_compression(
        self,
        audio: np.ndarray,
        threshold_db: float = -20.0,
        ratio: float = 4.0,
        attack_ms: float = 10,
        release_ms: float = 100,
    ) -> np.ndarray:
        """Apply dynamic range compression."""
        threshold = 10 ** (threshold_db / 20)
        attack_samples = max(1, int(attack_ms * self.sr / 1000))
        release_samples = max(1, int(release_ms * self.sr / 1000))

        compressed = np.zeros_like(audio)
        gain = 1.0

        for i in range(len(audio)):
            abs_val = abs(audio[i])
            if abs_val > threshold:
                excess_db = 20 * np.log10(abs_val / threshold)
                gain_reduction_db = -excess_db * (1 - 1 / ratio)
                target_gain = 10 ** (gain_reduction_db / 20)
                gain = gain + (target_gain - gain) / attack_samples
            else:
                gain = gain + (1.0 - gain) / release_samples

            compressed[i] = audio[i] * gain

        return compressed

    def _bandpass_filter(
        self, audio: np.ndarray, low_freq: float = 80, high_freq: float = 8000
    ) -> np.ndarray:
        """Apply bandpass filter for voice frequency range."""
        try:
            from scipy.signal import butter, filtfilt

            b, a = butter(4, [low_freq / (self.sr / 2), high_freq / (self.sr / 2)], btype="band")
            return filtfilt(b, a, audio)
        except ImportError:
            return audio

    @staticmethod
    def _compute_rms(audio: np.ndarray) -> float:
        return float(np.sqrt(np.mean(audio ** 2)))

    @staticmethod
    def _peak_db(audio: np.ndarray) -> float:
        peak = np.max(np.abs(audio))
        return float(20 * np.log10(max(peak, 1e-10)))

    def get_audio_stats(self, audio: np.ndarray) -> Dict[str, float]:
        """Get comprehensive audio statistics."""
        return {
            "rms": self._compute_rms(audio),
            "peak_db": self._peak_db(audio),
            "duration_seconds": len(audio) / self.sr,
            "sample_count": len(audio),
            "dynamic_range_db": self._peak_db(audio) - (20 * np.log10(max(self._compute_rms(audio), 1e-10))),
            "zero_crossing_rate": float(np.mean(np.abs(np.diff(np.sign(audio)))) / 2),
        }


audio_enhancement = AudioEnhancementService()

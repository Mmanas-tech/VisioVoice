"""Multi-backend Text-to-Speech service."""

import logging
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 22050


class TextToSpeechService:
    """Multi-backend TTS service supporting Google, Bark, ElevenLabs, pyttsx3, and local models."""

    def __init__(self, backend: str = "pyttsx3", **kwargs):
        self.backend = backend
        self.sample_rate = SAMPLE_RATE
        self._engine = None
        self._client = None
        self._elevenlabs_client = None
        self._bark_ready = False
        self._config = kwargs

        if backend == "google":
            self._init_google_tts(**kwargs)
        elif backend == "bark":
            self._init_bark(**kwargs)
        elif backend == "elevenlabs":
            self._init_elevenlabs(**kwargs)
        elif backend == "pyttsx3":
            self._init_pyttsx3()
        else:
            logger.warning(f"Unknown TTS backend: {backend}, falling back to pyttsx3")
            self._init_pyttsx3()

    def _init_pyttsx3(self):
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 150)
            self._engine.setProperty("volume", 1.0)
            logger.info("pyttsx3 TTS engine initialized")
        except (ImportError, RuntimeError) as e:
            logger.warning(f"pyttsx3 initialization failed: {e}")
            self._engine = None

    def _init_google_tts(self, **kwargs):
        try:
            from google.cloud import texttospeech
            self._client = texttospeech.TextToSpeechClient()
            logger.info("Google Cloud TTS initialized")
        except ImportError:
            logger.warning("google-cloud-texttospeech not available")
            self._client = None

    def _init_bark(self, **kwargs):
        try:
            from bark import preload_models
            preload_models()
            logger.info("Bark TTS initialized")
            self._bark_ready = True
        except ImportError:
            logger.warning("Bark not available")
            self._bark_ready = False

    def _init_elevenlabs(self, **kwargs):
        try:
            from elevenlabs.client import ElevenLabs
            api_key = kwargs.get("api_key") or os.environ.get("ELEVENLABS_API_KEY")
            if api_key:
                self._elevenlabs_client = ElevenLabs(api_key=api_key)
                logger.info("ElevenLabs TTS initialized")
            else:
                logger.warning("ElevenLabs API key not provided")
                self._elevenlabs_client = None
        except ImportError:
            logger.warning("elevenlabs not available")
            self._elevenlabs_client = None

    def synthesize(
        self,
        text: str,
        language: str = "en-US",
        voice_name: str = "default",
        pitch: float = 0.0,
        speaking_rate: float = 1.0,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesize speech from text.

        Args:
            text: Input text to synthesize
            language: Language code
            voice_name: Voice identifier
            pitch: Pitch adjustment (-20 to 20)
            speaking_rate: Speed multiplier (0.25 to 4.0)
            output_path: Optional path to save audio

        Returns:
            Dict with audio array, sample rate, duration, metadata
        """
        start_time = time.time()

        if self.backend == "google" and self._client:
            result = self._synthesize_google(text, language, voice_name, pitch, speaking_rate)
        elif self.backend == "bark" and self._bark_ready:
            result = self._synthesize_bark(text, voice_name, language)
        elif self.backend == "elevenlabs" and self._elevenlabs_client:
            result = self._synthesize_elevenlabs(text, voice_name)
        elif self._engine:
            result = self._synthesize_pyttsx3(text, output_path)
        else:
            result = self._synthesize_fallback(text)

        synthesis_time = (time.time() - start_time) * 1000

        audio = result["audio"]
        duration = len(audio) / self.sample_rate

        if output_path and not result.get("saved"):
            self._save_audio(audio, output_path)

        return {
            "audio": audio,
            "sample_rate": self.sample_rate,
            "duration_seconds": round(duration, 3),
            "backend": self.backend,
            "synthesis_time_ms": round(synthesis_time, 2),
            "text": text,
            "voice": voice_name,
            "output_path": output_path,
        }

    def _synthesize_google(
        self, text: str, language: str, voice_name: str, pitch: float, speaking_rate: float
    ) -> Dict[str, Any]:
        """Synthesize using Google Cloud TTS."""
        from google.cloud.texttospeech import SynthesisInput, VoiceSelectionParams, AudioConfig

        synthesis_input = SynthesisInput(text=text)
        voice = VoiceSelectionParams(language_code=language, name=voice_name)
        audio_config = AudioConfig(
            audio_encoding="LINEAR16",
            sample_rate_hertz=self.sample_rate,
            pitch=pitch,
            speaking_rate=speaking_rate,
        )

        response = self._client.synthesize_speech(
            request={"input": synthesis_input, "voice": voice, "audio_config": audio_config}
        )

        audio_np = np.frombuffer(response.audio_content, dtype=np.int16).astype(np.float32) / 32768.0
        return {"audio": audio_np}

    def _synthesize_bark(self, text: str, voice: str, language: str) -> Dict[str, Any]:
        """Synthesize using Bark."""
        from bark import generate_audio

        speaker_prompt = f"v2/en_speaker_0" if voice == "default" else voice
        audio = generate_audio(text, history_prompt=speaker_prompt)
        return {"audio": np.array(audio, dtype=np.float32)}

    def _synthesize_elevenlabs(self, text: str, voice_name: str) -> Dict[str, Any]:
        """Synthesize using ElevenLabs."""
        voice_id = voice_name if voice_name != "default" else "21m00Tcm4TlvDq8ikWAM"

        audio_generator = self._elevenlabs_client.generate(
            text=text,
            voice=voice_name,
            model="eleven_monolingual_v1",
        )

        audio_bytes = b"".join(audio_generator)

        import io
        import soundfile as sf
        audio, sr = sf.read(io.BytesIO(audio_bytes))
        if sr != self.sample_rate:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
        return {"audio": audio.astype(np.float32)}

    def _synthesize_pyttsx3(self, text: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Synthesize using pyttsx3."""
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

        self._engine.save_to_file(text, output_path)
        self._engine.runAndWait()

        try:
            import soundfile as sf
            audio, sr = sf.read(output_path)
            if sr != self.sample_rate:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
            return {"audio": audio.astype(np.float32), "saved": True}
        except Exception:
            return {"audio": np.zeros(self.sample_rate, dtype=np.float32), "saved": False}

    def _synthesize_fallback(self, text: str) -> Dict[str, Any]:
        """Minimal fallback TTS using sine wave synthesis."""
        duration = max(0.5, len(text) * 0.05)
        t = np.linspace(0, duration, int(self.sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * 440 * t) * np.exp(-t * 2)
        return {"audio": audio.astype(np.float32)}

    def _save_audio(self, audio: np.ndarray, output_path: str):
        """Save audio array to file."""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        try:
            import soundfile as sf
            sf.write(output_path, audio, self.sample_rate, subtype="PCM_16")
        except ImportError:
            import wave
            with wave.open(output_path, "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                audio_int16 = (audio * 32767).astype(np.int16)
                wf.writeframes(audio_int16.tobytes())

    def synthesize_segments(
        self,
        segments: List[Dict[str, Any]],
        output_dir: str,
        voice_params: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """Synthesize audio for multiple transcription segments."""
        os.makedirs(output_dir, exist_ok=True)
        results = []

        for i, seg in enumerate(segments):
            text = seg.get("text", "")
            if not text.strip():
                continue

            output_path = os.path.join(output_dir, f"segment_{i:04d}.wav")
            voice_params = voice_params or {}

            result = self.synthesize(
                text=text,
                output_path=output_path,
                **voice_params,
            )
            result["segment_index"] = i
            result["start_ms"] = seg.get("start_ms", 0)
            result["end_ms"] = seg.get("end_ms", 0)
            results.append(result)

        return results

    @property
    def available_backends(self) -> List[str]:
        """List available TTS backends."""
        backends = ["fallback"]
        if self._engine:
            backends.append("pyttsx3")
        if self._client:
            backends.append("google")
        if self._bark_ready:
            backends.append("bark")
        if self._elevenlabs_client:
            backends.append("elevenlabs")
        return backends


tts_service = TextToSpeechService(backend="pyttsx3")

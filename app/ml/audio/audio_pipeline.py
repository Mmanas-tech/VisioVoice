"""Complete audio synthesis pipeline integrating all audio services."""

import logging
import os
import time
from typing import Any, Dict, List, Optional

import numpy as np

from app.ml.audio.tts_service import TextToSpeechService
from app.ml.audio.audio_enhancement import AudioEnhancementService
from app.ml.audio.lipsync_service import LipSyncAlignmentService
from app.ml.audio.audio_export import AudioExportService
from app.ml.audio.subtitle_service import SubtitleService

logger = logging.getLogger(__name__)


class AudioSynthesisPipeline:
    """Complete end-to-end audio synthesis pipeline."""

    def __init__(
        self,
        tts_backend: str = "pyttsx3",
        sample_rate: int = 22050,
        enable_enhancement: bool = True,
        enable_lipsync: bool = True,
    ):
        self.sample_rate = sample_rate
        self.enable_enhancement = enable_enhancement
        self.enable_lipsync = enable_lipsync

        self.tts = TextToSpeechService(backend=tts_backend)
        self.enhancement = AudioEnhancementService(sample_rate=sample_rate)
        self.lipsync = LipSyncAlignmentService()
        self.export = AudioExportService(sample_rate=sample_rate)
        self.subtitles = SubtitleService()

    def synthesize_from_transcription(
        self,
        transcription_text: str,
        transcription_segments: List[Dict],
        video_duration_seconds: float,
        video_fps: int = 25,
        output_dir: str = "./output",
        export_formats: Optional[List[str]] = None,
        voice_params: Optional[Dict] = None,
        generate_subtitles: bool = True,
    ) -> Dict[str, Any]:
        """
        Complete synthesis pipeline.

        Args:
            transcription_text: Full transcription text
            transcription_segments: List of {start_ms, end_ms, text}
            video_duration_seconds: Original video duration
            video_fps: Video frame rate
            output_dir: Output directory
            export_formats: List of formats (wav, mp3, flac, aac, ogg)
            voice_params: TTS voice parameters
            generate_subtitles: Generate subtitle files

        Returns:
            Dict with audio files, subtitles, metadata
        """
        start_time = time.time()
        export_formats = export_formats or ["wav", "mp3"]
        voice_params = voice_params or {}

        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Starting audio synthesis pipeline in {output_dir}")

        # Step 1: TTS Synthesis
        logger.info("Step 1/5: Synthesizing speech from text...")
        tts_result = self.tts.synthesize(
            transcription_text,
            language=voice_params.get("language", "en-US"),
            voice_name=voice_params.get("voice", "default"),
            pitch=voice_params.get("pitch", 0.0),
            speaking_rate=voice_params.get("speaking_rate", 1.0),
        )
        audio = tts_result["audio"]
        logger.info(f"TTS completed: {tts_result['duration_seconds']:.2f}s audio")

        # Step 2: Audio Enhancement
        enhancement_result = None
        if self.enable_enhancement:
            logger.info("Step 2/5: Enhancing audio quality...")
            enhancement_result = self.enhancement.enhance_audio(
                audio, denoise=True, normalize=True, equalize=True, compress=True
            )
            audio = enhancement_result["audio"]
            logger.info(f"Enhancement applied: {enhancement_result['enhancement_applied']}")
        else:
            logger.info("Step 2/5: Enhancement skipped")

        # Step 3: Lip-Sync Alignment
        lipsync_result = None
        if self.enable_lipsync and transcription_segments:
            logger.info("Step 3/5: Aligning audio to video...")
            lipsync_result = self.lipsync.align_audio_to_video(
                audio, video_duration_seconds, transcription_segments, self.sample_rate
            )
            audio = lipsync_result["aligned_audio"]
            logger.info(f"Lip-sync: confidence={lipsync_result['confidence']:.2%}")
        else:
            logger.info("Step 3/5: Lip-sync skipped")

        # Step 4: Export Audio
        logger.info("Step 4/5: Exporting audio files...")
        export_results = {}
        for fmt in export_formats:
            output_path = os.path.join(output_dir, f"output.{fmt}")
            result = self.export.export_audio(
                audio, output_path, format=fmt,
                metadata={"title": "Lip-Reading AI Synthesis", "artist": "VisoVoice AI"},
            )
            export_results[fmt] = result

        # Step 5: Generate Subtitles
        subtitle_results = {}
        if generate_subtitles and transcription_segments:
            logger.info("Step 5/5: Generating subtitles...")
            subtitle_results = self.subtitles.generate_all_formats(
                transcription_segments, output_dir
            )
        else:
            logger.info("Step 5/5: Subtitles skipped")

        total_time = time.time() - start_time

        return {
            "audio_files": export_results,
            "subtitle_files": subtitle_results,
            "metadata": {
                "original_text": transcription_text,
                "audio_duration_seconds": round(len(audio) / self.sample_rate, 3),
                "num_segments": len(transcription_segments),
                "total_processing_time_seconds": round(total_time, 3),
                "tts_backend": self.tts.backend,
                "sample_rate": self.sample_rate,
                "enhancements_applied": (
                    enhancement_result["enhancement_applied"] if enhancement_result else []
                ),
                "lipsync_confidence": (
                    lipsync_result["confidence"] if lipsync_result else None
                ),
                "output_dir": output_dir,
            },
        }

    def synthesize_segment_audio(
        self,
        segments: List[Dict],
        output_dir: str,
        voice_params: Optional[Dict] = None,
    ) -> List[Dict]:
        """Synthesize individual audio files for each segment."""
        os.makedirs(output_dir, exist_ok=True)
        results = self.tts.synthesize_segments(segments, output_dir, voice_params)

        for result in results:
            if self.enable_enhancement and "output_path" in result:
                try:
                    import soundfile as sf
                    audio, sr = sf.read(result["output_path"])
                    enhanced = self.enhancement.enhance_audio(audio.astype(np.float32))
                    sf.write(result["output_path"], enhanced["audio"], sr)
                except Exception as e:
                    logger.warning(f"Enhancement failed for segment: {e}")

        return results


def create_audio_pipeline(
    tts_backend: str = "pyttsx3",
    enable_enhancement: bool = True,
    enable_lipsync: bool = True,
) -> AudioSynthesisPipeline:
    """Factory function to create an audio synthesis pipeline."""
    return AudioSynthesisPipeline(
        tts_backend=tts_backend,
        enable_enhancement=enable_enhancement,
        enable_lipsync=enable_lipsync,
    )

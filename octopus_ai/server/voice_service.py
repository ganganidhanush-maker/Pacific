"""
Voice Service for Octopus AI Desktop Agent
Replicates user's voice (Dhanush) using Resemble AI Chatterbox Turbo/Nano with CUDA GPU acceleration.
Includes smart audio caching for instant zero-latency responses on repeated phrases.
"""

import os
import sys
import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("OctopusVoiceService")

# Root directory resolution
ROOT_DIR = Path(__file__).resolve().parent.parent
VOICE_REF_DIR = ROOT_DIR / "assets" / "voice_reference"
AUDIO_CACHE_DIR = ROOT_DIR / "assets" / "audio_cache"
CONDS_PATH = VOICE_REF_DIR / "dhanush_voice_conds.pt"
REF_15S_PATH = VOICE_REF_DIR / "dhanush_voice_ref_15s.wav"
REF_10S_PATH = VOICE_REF_DIR / "dhanush_voice_ref_10s.wav"
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class VoiceService:
    _instance: Optional["VoiceService"] = None

    def __init__(self):
        self.model = None
        self.device = "cpu"
        self.sr = 24000
        self.initialized = False
        self.init_error = None

    @classmethod
    def get_instance(cls) -> "VoiceService":
        if cls._instance is None:
            cls._instance = VoiceService()
        return cls._instance

    def initialize(self) -> bool:
        """
        Initializes Chatterbox model and loads Dhanush's voice conditionals.
        CUDA GPU (RTX 4050) is used when available.
        """
        if self.initialized:
            return True

        try:
            import torch
            import torchaudio as ta
            from chatterbox.tts_turbo import ChatterboxTurboTTS, Conditionals

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[VoiceService] Initializing Chatterbox Turbo on {self.device.upper()}...")
            if self.device == "cuda":
                gpu_name = torch.cuda.get_device_name(0)
                print(f"[VoiceService] Hardware Acceleration Active: {gpu_name}")

            # Load Chatterbox Turbo model
            self.model = ChatterboxTurboTTS.from_pretrained(device=self.device)
            self.sr = self.model.sr

            # Load precomputed conditionals if available, or compute and cache them
            if CONDS_PATH.exists():
                print(f"[VoiceService] Loading precomputed voice conditionals: {CONDS_PATH.name}")
                map_loc = None if self.device == "cuda" else torch.device("cpu")
                self.model.conds = Conditionals.load(CONDS_PATH, map_location=map_loc).to(self.device)
            elif REF_15S_PATH.exists():
                print(f"[VoiceService] Conditioning model with reference audio: {REF_15S_PATH.name}")
                self.model.prepare_conditionals(str(REF_15S_PATH), exaggeration=0.2, norm_loudness=True)
                try:
                    self.model.conds.save(CONDS_PATH)
                    print(f"[VoiceService] Saved voice conditionals to {CONDS_PATH.name}")
                except Exception as save_err:
                    print(f"[VoiceService] Could not save conditionals cache: {save_err}")
            elif REF_10S_PATH.exists():
                print(f"[VoiceService] Conditioning model with 10s reference: {REF_10S_PATH.name}")
                self.model.prepare_conditionals(str(REF_10S_PATH), exaggeration=0.2, norm_loudness=True)
                try:
                    self.model.conds.save(CONDS_PATH)
                except Exception:
                    pass
            else:
                print("[VoiceService] Warning: No voice reference files found in assets/voice_reference/!")

            self.initialized = True
            print("[VoiceService] Dhanush Voice Cloning Engine Ready!")
            return True

        except Exception as e:
            self.init_error = str(e)
            print(f"[VoiceService] Initialization warning/fallback: {e}")
            return False

    async def generate_speech_file(self, text: str, voice: Optional[str] = None) -> Optional[str]:
        """
        Generates speech matching Dhanush's voice or target language voice.
        Supports native Telugu (te-IN-MohanNeural), Hindi, English, and all world languages.
        Caches synthesized audio by text & voice hash for immediate 0ms response on repeated phrases.
        Returns web-accessible relative URL: /assets/audio_cache/<hash>.[wav|mp3]
        """
        cleaned_text = text.strip()
        if not cleaned_text:
            return None

        # Determine target voice if not explicitly provided
        target_voice = voice
        if not target_voice:
            # Check for Telugu script (\u0c00-\u0c7f)
            if any('\u0c00' <= ch <= '\u0c7f' for ch in cleaned_text):
                target_voice = "te-IN-MohanNeural"
            # Check for Devanagari / Hindi script (\u0900-\u097f)
            elif any('\u0900' <= ch <= '\u097f' for ch in cleaned_text):
                target_voice = "hi-IN-MadhurNeural"
            # Check for Tamil (\u0b80-\u0bff)
            elif any('\u0b80' <= ch <= '\u0bff' for ch in cleaned_text):
                target_voice = "ta-IN-ValluvarNeural"
            # Check for Kannada (\u0c80-\u0cff)
            elif any('\u0c80' <= ch <= '\u0cff' for ch in cleaned_text):
                target_voice = "kn-IN-GaganNeural"
            # Check for Malayalam (\u0d00-\u0d7f)
            elif any('\u0d00' <= ch <= '\u0d7f' for ch in cleaned_text):
                target_voice = "ml-IN-MidhunNeural"
            else:
                target_voice = "en-IN-PrabhatNeural"

        # Build unique cache key including target voice and volume setting
        cache_key = f"dhanush_voice_maxvol_{target_voice}:{cleaned_text.lower()}"
        text_hash = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
        filename = f"{text_hash}.wav"
        filepath = AUDIO_CACHE_DIR / filename

        # Return cached audio if already generated
        if filepath.exists() and filepath.stat().st_size > 1000:
            return f"/assets/audio_cache/{filename}"

        # If Chatterbox model is not initialized and English is targeted, try initializing
        # Chatterbox is English-only; for Telugu and other languages, Edge-TTS provides native neural synthesis
        is_english = target_voice.startswith("en-")
        if is_english and not self.initialized:
            self.initialize()

        if is_english and self.initialized and self.model is not None:
            try:
                import torch
                import torchaudio as ta
                import numpy as np

                # Synthesize with Chatterbox
                wav = self.model.generate(
                    cleaned_text,
                    temperature=0.8,
                    top_k=1000,
                    top_p=0.95,
                    repetition_penalty=1.2
                )

                # Save waveform using soundfile with maximum peak normalization
                import soundfile as sf
                audio_np = wav.squeeze().cpu().numpy()
                max_val = np.max(np.abs(audio_np))
                if max_val > 0:
                    audio_np = (audio_np / max_val) * 0.98
                sf.write(str(filepath), audio_np, self.model.sr)
                return f"/assets/audio_cache/{filename}"
            except Exception as gen_err:
                print(f"[VoiceService] Synthesis error ({gen_err}), falling back to Edge TTS...")

        # Native Edge-TTS for Telugu, Hindi, Tamil, and high-quality voice synthesis at maximum volume
        try:
            import edge_tts
            fallback_filename = f"{text_hash}.mp3"
            fallback_path = AUDIO_CACHE_DIR / fallback_filename
            if not fallback_path.exists() or fallback_path.stat().st_size == 0:
                communicate = edge_tts.Communicate(cleaned_text, voice=target_voice, volume="+100%")
                await communicate.save(str(fallback_path))
            return f"/assets/audio_cache/{fallback_filename}"
        except Exception as fb_err:
            print(f"[VoiceService] Fallback TTS error with {target_voice}: {fb_err}")
            return None


# Global singleton instance
voice_service_instance = VoiceService.get_instance()

async def synthesize_dhanush_voice(text: str, voice: Optional[str] = None) -> Optional[str]:
    return await voice_service_instance.generate_speech_file(text, voice=voice)


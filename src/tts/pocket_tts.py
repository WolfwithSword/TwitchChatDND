import asyncio
import threading
import os
import glob
import struct
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import pocket_tts_bindings

from tts.tts import TTS, create_wav_header
from helpers.instance_manager import get_config
from helpers.utils import run_coroutine_sync, try_get_cache
from helpers.constants import TTS_SOURCE
from custom_logger.logger import logger

from chatdnd.events.tts_events import (
    on_pocket_tts_connect,
    request_pocket_tts_connect,
    on_pocket_tts_test_speak
)

from data.voices import _upsert_voice, fetch_voices, get_all_voice_ids, delete_voice
from data.member import remove_tts
import threading
from elevenlabs import play


# Pocket TTS specific settings
POCKET_TTS_SAMPLE_RATE = 24000  # Pocket TTS generates at 24kHz
MODEL_VARIANT = "b6369a24"

tts_executor = ProcessPoolExecutor(max_workers=1)
def generate_audio_process(model_path, text, voice_id):
    import pocket_tts_bindings

    model = pocket_tts_bindings.PyTTSModel.load_from_paths(
        model_path,
        device="cpu"
    )

    samples = model.generate(text, voice_id)

    # Convert to bytes here to reduce IPC cost
    import struct
    scaled = [max(-32768, min(32767, int(s * 32767))) for s in samples]
    return struct.pack('<' + 'h' * len(scaled), *scaled)


class PocketTTS(TTS):
    source_type = TTS_SOURCE.SOURCE_POCKET


    def __init__(self):
        super().__init__()
        self.client = None
        request_pocket_tts_connect.addListener(self.setup)

        self.setup()
        on_pocket_tts_test_speak.addListener(self.test_speak)

        # Override base class settings to match Pocket TTS
        self.sample_rate = POCKET_TTS_SAMPLE_RATE
        self.bits_per_sample = 16
        self.num_channels = 1

    @property
    def voices(self) -> dict:
        """Return available voices from the voices directory."""
        d = {}
        _voices = run_coroutine_sync(fetch_voices(source=self.source_type))
        for v in _voices:
            if v:
                d.setdefault(f"{v.name} ({v.uid})", v.uid)
        return d

    def setup(self):
        """Initialize Pocket TTS model."""
        on_pocket_tts_connect.trigger([False])
        
        try:
            logger.info("Loading Pocket TTS model...")
            logger.debug(f"Configured Pocket TTS model path: ")
            
            # Get model path from config
            config = get_config(name="default")
            model_path = config.get(section="POCKET_TTS", option="model_path", fallback="")
            
            if model_path and os.path.exists(model_path):
                # Load model from custom path
                logger.info(f"Loading Pocket TTS model from: {model_path}")
                
                # Ensure path is properly formatted for the bindings
                model_path = os.path.abspath(model_path)
                
                # Handle potential path issues (spaces, special characters, etc.)
                # Try multiple approaches to load the model
                load_attempts = [
                    # 1. Try with absolute path as-is
                    model_path,
                    # 2. Try with forward slashes (some libraries prefer this)
                    model_path.replace('\\', '/'),
                    # 3. Try with escaped backslashes
                    model_path.replace('\\', '\\\\'),
                    # 4. Try with just the filename in current directory
                    os.path.basename(model_path),
                    # 5. Try copying to current directory and loading
                ]
                
                for i, attempt_path in enumerate(load_attempts):
                    try:
                        if i == 4:  # Last attempt - copy to current directory
                            import shutil
                            filename = os.path.basename(model_path)
                            local_copy = os.path.join(os.getcwd(), filename)
                            if not os.path.exists(local_copy):
                                shutil.copy2(model_path, local_copy)
                            attempt_path = filename
                        
                        logger.debug(f"Attempt {i+1}: Trying path: {attempt_path}")
                        self.client = pocket_tts_bindings.PyTTSModel.load_from_paths(attempt_path,device="cpu")
                        self.model_path = attempt_path
                        logger.info(f"✅ Pocket TTS model loaded successfully (attempt {i+1})")
                        break
                        
                    except Exception as load_error:
                        if i < len(load_attempts) - 1:
                            logger.debug(f"Attempt {i+1} failed: {load_error}")
                            continue
                        else:
                            logger.error(f"All loading attempts failed: {load_error}")
                            raise load_error
            else:
                # Do not attempt to load if path is invalid
                logger.warning("Pocket TTS model path is not set or does not exist. Skipping model loading.")
                on_pocket_tts_connect.trigger([False])
            
            on_pocket_tts_connect.trigger([True])
        except Exception as e:
            logger.error(f"❌ Failed to load Pocket TTS model: {e}")
            on_pocket_tts_connect.trigger([False])

    def _float_samples_to_bytes(self, samples):
        """Convert float audio samples to 16-bit PCM bytes."""
        # Scale float samples to 16-bit integers
        scaled = [max(-32768, min(32767, int(s * 32767))) for s in samples]
        
        # Pack as little-endian 16-bit integers
        return struct.pack('<' + 'h' * len(scaled), *scaled)

    async def get_stream(self, text="Hello World!", voice_id: str = None):
        """Generate audio stream from text using Pocket TTS."""
        if not voice_id or not self.client:
            yield None, None

        try:
            # Generate full audio using Pocket TTS
            audio_samples = await asyncio.to_thread(self.client.generate, text, voice_id)
            # audio_bytes = self._float_samples_to_bytes(audio_samples)
            audio_bytes = await asyncio.get_event_loop().run_in_executor(
                tts_executor,
                generate_audio_process,
                self.model_path,
                text,
                voice_id
            )

            if not audio_bytes:
                yield None, None
                return

            # Stream in chunks, each with its own WAV header for proper browser decoding
            chunk_size = self.max_chunk_size
            offset = 0
            total_samples = len(audio_bytes)

            while offset < total_samples:
                # Get chunk of raw PCM data
                chunk = audio_bytes[offset:offset + chunk_size]
                chunk_len = len(chunk)

                # Create WAV header for this specific chunk
                header = create_wav_header(
                    self.sample_rate,
                    self.bits_per_sample,
                    self.num_channels,
                    chunk_len
                )

                # Calculate duration for this chunk
                duration = chunk_len / (self.sample_rate * self.num_channels * (self.bits_per_sample // 8))

                # Sleep to pace the chunks (matches behavior of other TTS providers)
                await asyncio.sleep(duration)

                # Send header + chunk data
                yield (header + chunk, duration)

                offset += chunk_size

        except Exception as e:
            logger.error(f"Pocket TTS streaming failed: {e}")
            yield None, None

    def create_voice_from_wav(self, wav_path: str, voice_name: str = None) -> dict | None:
        """Create a safetensor voice from a WAV file and add it to the database.
        
        Args:
            wav_path: Path to the WAV file
            voice_name: Optional name for the voice. If not provided, uses the filename.
            
        Returns:
            Voice object with name and uid, or None if creation failed
        """
        if not self.client:
            logger.error("Pocket TTS: Cannot create voice - model not loaded")
            return None
            
        # Validate WAV file exists
        if not os.path.exists(wav_path):
            logger.error(f"Pocket TTS: WAV file not found: {wav_path}")
            return None
            
        # Get voices directory from config
        config = get_config(name="default")
        voices_dir = config.get(section="POCKET_TTS", option="voices_dir", fallback="voices")
        
        # Ensure voices directory exists
        if not os.path.exists(voices_dir):
            os.makedirs(voices_dir, exist_ok=True)
            logger.info(f"Created voices directory: {voices_dir}")
            
        # Generate safetensors path in voices directory
        wav_path = os.path.abspath(wav_path)
        filename = Path(wav_path).stem
        safetensors_path = os.path.join(voices_dir, f"{filename}.safetensors")
        
        # Use provided name or generate from filename
        if voice_name is None:
            voice_name = filename
            
        try:
            logger.info(f"Converting {wav_path} to {safetensors_path}")
            
            # Convert WAV to safetensors using Pocket TTS model
            self.client.save_audio_as_voice_prompt(wav_path, safetensors_path)
            
            # Add to database
            voice_obj = run_coroutine_sync(_upsert_voice(
                name=voice_name, 
                uid=safetensors_path, 
                source=self.source_type
            ))
            
            logger.info(f"✅ Successfully created voice '{voice_name}' from {wav_path}")
            return {"name": voice_name, "uid": safetensors_path}
            
        except Exception as e:
            logger.error(f"Pocket TTS: Failed to create voice from {wav_path}: {e}")
            return None

    def get_voice_object(self, voice_id: str = "", run_sync_always: bool = False) -> dict | None:
        """Get voice object for the given voice ID."""
        if not voice_id:
            return None

        # Check if voice file exists
        if not os.path.exists(voice_id):
            logger.warning(f"Pocket TTS Voice file '{voice_id}' not found")
            return None

        voice_name = Path(voice_id).stem
        
        if run_sync_always:
            run_coroutine_sync(_upsert_voice(name=voice_name, uid=voice_id, source=self.source_type))
        elif asyncio.get_event_loop():
            asyncio.create_task(_upsert_voice(name=voice_name, uid=voice_id, source=self.source_type))
        else:
            run_coroutine_sync(_upsert_voice(name=voice_name, uid=voice_id, source=self.source_type))

        return {"name": voice_name, "uid": voice_id}

    def list_voices(self) -> list:
        """List available voice files."""
        config = get_config(name="default")
        voices_dir = config.get(section="POCKET_TTS", option="voices_dir", fallback="voices")
        
        if not os.path.exists(voices_dir):
            return []
        
        voice_files = []
        voice_files.extend(glob.glob(os.path.join(voices_dir, "*.wav")))
        voice_files.extend(glob.glob(os.path.join(voices_dir, "*.safetensors")))
        
        return [Path(f).stem for f in voice_files]

    def search_for_voice_by_id(self, uid: str) -> dict | None:
        """Search for voice by ID (file path)."""
        if not uid:
            return None
        return self.get_voice_object(voice_id=uid, run_sync_always=False)

    @staticmethod
    def voices_messages() -> str:
        """Return message about how to add voices."""
        config = get_config(name="default")
        voices_dir = config.get(section="POCKET_TTS", option="voices_dir", fallback="voices")
        msg = (
            f"Add voice files (.wav or .safetensors) to the '{voices_dir}' directory. "
            "WAV files will be automatically converted to .safetensors for faster loading."
        )
        return msg

    def voice_list_message(self) -> str:
        """Return formatted voice list message."""
        return PocketTTS.voices_messages()

    def test_speak(self, text: str = "Hello there. How are you?", voice_id: str = None):
        """Test speaking with the specified voice."""
        if not voice_id or not self.client:
            logger.warning("Pocket TTS: No voice ID or client available for test speak")
            return
        
        loop = asyncio.get_event_loop()
        async def run():
            audio_bytes = await loop.run_in_executor(
                tts_executor,
                generate_audio_process,
                self.model_path,
                text,
                voice_id
            )

            header = create_wav_header(
                self.sample_rate,
                self.bits_per_sample,
                self.num_channels,
                len(audio_bytes)
            )

            play(iter([header + audio_bytes]))

        asyncio.create_task(run())

        # Handle WAV file conversion using the new function
        # voice_path = voice_id

        # def preview_audio_th():
        #     try:
        #         # Generate audio
        #         audio_samples = self.client.generate(text, voice_path)
        #         audio_bytes = self._float_samples_to_bytes(audio_samples)

        #         # Create WAV header
        #         header = create_wav_header(
        #             self.sample_rate,
        #             self.bits_per_sample,
        #             self.num_channels,
        #             len(audio_bytes)
        #         )

        #         # Combine header and audio data
        #         full_audio = header + audio_bytes

        #         # Use elevenlabs play for playback - pass as iterator
        #         play(iter([full_audio]))

        #     except Exception as e:
        #         logger.error(f"Pocket TTS test speak failed: {e}")

        # # Run in separate thread to avoid blocking UI
        # thread = threading.Thread(target=preview_audio_th)
        # thread.daemon = True
        # thread.start()

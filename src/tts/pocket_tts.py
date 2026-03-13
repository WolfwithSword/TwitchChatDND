import asyncio
import os
import glob
import struct
from pathlib import Path

import pocket_tts_bindings

from tts.tts import TTS, create_wav_header
from helpers.instance_manager import get_config
from helpers.utils import run_coroutine_sync
from helpers.constants import TTS_SOURCE
from custom_logger.logger import logger

from chatdnd.events.tts_events import (
    on_pocket_tts_connect,
    request_pocket_tts_connect,
    on_pocket_tts_test_speak
)

from data.voices import _upsert_voice, fetch_voices
from elevenlabs import play


# Pocket TTS specific settings
POCKET_TTS_SAMPLE_RATE = 24000  # Pocket TTS generates at 24kHz


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
                return

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

    async def get_stream(self, text="Hello World!", voice_id: str = None, use_chunked: bool = True):
        """Generate audio stream from text using Pocket TTS.
        
        Args:
            text: Text to synthesize
            voice_id: Path to voice file (.wav or .safetensors)
            use_chunked: If True, use streaming generation (lower latency). 
                        If False, generate full audio first then stream.
                        Default is True for Pocket TTS.
        """
        if not voice_id or not self.client:
            yield None, None
            return

        if use_chunked:
            async for chunk, duration in self._get_stream_chunked(text, voice_id):
                yield (chunk, duration)
        else:
            async for chunk, duration in self._get_stream_full(text, voice_id):
                yield (chunk, duration)

    async def _get_stream_full(self, text="Hello World!", voice_id: str = None):
        """Generate full audio first, then stream in chunks (legacy behavior)."""
        try:
            # Generate full audio using Pocket TTS
            audio_bytes = await asyncio.to_thread(
                self.client.generate, text, voice_id
            )
            audio_bytes = self._float_samples_to_bytes(audio_bytes)

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

    async def _get_stream_chunked(self, text="Hello World!", voice_id: str = None):
        """Generate audio stream using chunked generation (lower latency).
        
        Uses the Pocket TTS streaming API to generate audio frames as they're ready,
        rather than waiting for the full audio to be generated first.
        
        Each chunk is a complete WAV file for independent browser decoding.
        
        Yields:
            Tuple of (bytes, float): WAV chunk bytes and duration in seconds
        """
        if not voice_id or not self.client:
            yield None, None
            return

        try:
            # Use the chunked generation API from the bindings
            # This returns an iterator of float chunks (one Mimi frame per chunk)
            chunked_iterator = await asyncio.to_thread(
                self.client.generate_chunked, text, voice_id
            )

            # Accumulate samples for batching into network-friendly chunks
            accumulated_samples = []
            target_chunk_samples = 18000  # 0.75 seconds at 24kHz - network chunk size
            initial_buffer_samples = 12000  # 0.5 seconds at 24kHz - initial buffer to prevent clipping
            has_initial_buffer = False
            chunk_count = 0

            for chunk_result in chunked_iterator:
                # chunk_result is a list of floats for one Mimi frame
                accumulated_samples.extend(chunk_result)

                # Build initial buffer before sending first chunk
                if not has_initial_buffer:
                    if len(accumulated_samples) >= initial_buffer_samples:
                        has_initial_buffer = True
                        logger.debug(f"Chunked TTS: Initial buffer ready ({len(accumulated_samples)} samples)")
                    continue

                # Send chunk when we have enough samples
                while len(accumulated_samples) >= target_chunk_samples:
                    frame_samples = accumulated_samples[:target_chunk_samples]
                    accumulated_samples = accumulated_samples[target_chunk_samples:]

                    # Convert to 16-bit PCM bytes
                    chunk_bytes = self._float_samples_to_bytes(frame_samples)

                    # Create complete WAV header for this chunk
                    # Each chunk must be independently decodable by the browser
                    header = create_wav_header(
                        self.sample_rate,
                        self.bits_per_sample,
                        self.num_channels,
                        len(chunk_bytes)
                    )

                    # Calculate duration
                    duration = len(frame_samples) / self.sample_rate
                    chunk_count += 1
                    
                    logger.debug(f"Chunked TTS: Sending chunk {chunk_count}, {len(frame_samples)} samples, {len(chunk_bytes)} bytes, {duration:.3f}s")

                    yield (header + chunk_bytes, duration)

            # Send any remaining samples
            if accumulated_samples:
                # If we never got enough for initial buffer, send everything as one chunk (short text)
                if not has_initial_buffer:
                    logger.debug(f"Chunked TTS: Short text, sending {len(accumulated_samples)} samples without buffering")
                
                chunk_bytes = self._float_samples_to_bytes(accumulated_samples)
                header = create_wav_header(
                    self.sample_rate,
                    self.bits_per_sample,
                    self.num_channels,
                    len(chunk_bytes)
                )

                duration = len(accumulated_samples) / self.sample_rate
                chunk_count += 1

                logger.debug(f"Chunked TTS: Sending final chunk {chunk_count}, {len(accumulated_samples)} samples, {len(chunk_bytes)} bytes, {duration:.3f}s")
                yield (header + chunk_bytes, duration)
            
            logger.info(f"Chunked TTS: Finished streaming {chunk_count} chunks for '{text[:50]}...'")

        except Exception as e:
            logger.error(f"Pocket TTS chunked streaming failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
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

        async def run():
            audio_samples = await asyncio.to_thread(
                self.client.generate, text, voice_id
            )
            audio_bytes = self._float_samples_to_bytes(audio_samples)

            header = create_wav_header(
                self.sample_rate,
                self.bits_per_sample,
                self.num_channels,
                len(audio_bytes)
            )

            play(iter([header + audio_bytes]))

        asyncio.create_task(run())

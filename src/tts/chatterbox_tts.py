import asyncio
import threading
import io
import os

import torch
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS as cbtts
from elevenlabs import play
from diskcache import Cache

from tts.tts import TTS, create_wav_header

from helpers import TCDNDConfig as Config
from helpers.utils import run_coroutine_sync
from helpers.constants import SOURCE_CHATTER

from custom_logger.logger import logger

from data.voices import _upsert_voice, fetch_voices, get_all_voice_ids

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class ChatterBoxTTS(TTS):
    def __init__(self, config: Config, full_instance: bool = True):
        super().__init__(config=None)

        self.model = cbtts.from_pretrained(DEVICE)
        self.sample_rate = self.model.sr

        self.config = config

        if full_instance:
            db_voice_ids = run_coroutine_sync(get_all_voice_ids(source=SOURCE_CHATTER))
            if not db_voice_ids or 'cbtts.default' not in db_voice_ids:
                run_coroutine_sync(_upsert_voice(name='Chatterbox Default', uid='cbtts.default', source=SOURCE_CHATTER))

        if config.getboolean(section="CACHE", option="enabled"):
            # Caching in general, but for here, it's specific to API results
            cache_dir = config.get(section="CACHE", option="directory", fallback=None)
            if not cache_dir:
                self.cache = Cache()
            else:
                self.cache = Cache(directory=cache_dir)
        else:
            self.cache = None
        self.cache = None ############

    @property
    def voices(self) -> dict:
        d = {}
        _voices = run_coroutine_sync(fetch_voices(source=SOURCE_CHATTER))
        for v in _voices:
            d.setdefault(f"{v.name}", v.uid)
        return d

    def list_voices(self) -> list:
        return [] # TODO

    def voice_list_message(self) -> str:
        voices = self.list_voices()
        return "ChatterBox Voices: " + ", ".join(voices)

    def audio_stream_generator(self, text="Hello World!", voice_id: str | None = None):
        output = io.BytesIO()
        if voice_id and voice_id != 'cbtts.default' and os.path.isfile(voice_id):
            wav = self.model.generate(
                text,
                audio_prompt_path=voice_id,
                exaggeration=0.62,
                temperature=0.75,
                cfg_weight=0.43)
        else:
            wav = self.model.generate(
                text,
                #audio_prompt_path="C:\\Users\\WolfwithSword\\Desktop\\something.mp3",
                exaggeration=0.62,
                temperature=0.75,
                cfg_weight=0.43)
        ta.save(output, wav, self.sample_rate, format='wav')
        output.seek(0)
        return output

    async def get_stream(self, text="Hello World!", voice_id: str | None = None):
        output = self.audio_stream_generator(text, voice_id)
        header = create_wav_header(
            self.sample_rate,
            self.bits_per_sample,
            self.num_channels,
            len(output.getvalue()),
        )
        chunk_size = min(self.max_chunk_size, len(output.getvalue()))
        chunk = output.read(chunk_size)

        while chunk:
            duration = len(chunk) / (self.sample_rate * self.num_channels * (self.bits_per_sample // 8))
            await asyncio.sleep(duration)
            yield (header + chunk, duration)
            chunk = output.read(chunk_size)

    def test_speak(self, text: str = "Hello there. How are you?", voice_id: str | None = None):

        key = f"cb.preview.{voice_id}"
        audio = None
        if self.cache is not None:
            audio_l = self.cache.get(key=key, default=None)
            if audio_l:
                audio = iter(audio_l)
                logger.debug(f"Fetched cached preview audio for `{voice_id}`")
        if not audio:
            def generate_and_play():
                audio = list(self.audio_stream_generator(text=text, voice_id=voice_id))
                if self.cache:
                    self.cache.set(
                        key=key,
                        expire=self.config.getint(
                            section="CACHE",
                            option="tts_cache_expiry",
                            fallback=7 * 24 * 60 * 60 * 4 * 3,
                        ),
                        value=list(audio),
                    )
                audio = iter(audio)
                play(audio)
            thread = threading.Thread(target=generate_and_play)
            thread.daemon = True
            thread.start()
            return
        thread = threading.Thread(target=play, args=(audio,))
        thread.daemon = True
        thread.start()

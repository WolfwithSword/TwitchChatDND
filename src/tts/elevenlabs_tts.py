import asyncio
import threading
import base64, io, struct

from tts.tts import TTS, create_wav_header

from elevenlabs.client import AsyncElevenLabs
from elevenlabs.client import ElevenLabs
from elevenlabs.types import Voice as ELVoice
from elevenlabs import play

from diskcache import Cache

from helpers import TCDNDConfig as Config
from helpers.utils import run_coroutine_sync
from helpers.constants import SOURCE_11L
from custom_logger.logger import logger

from chatdnd.events.tts_events import on_elevenlabs_connect, request_elevenlabs_connect, on_elevenlabs_test_speak

from data.voices import _upsert_voice, fetch_voices
from data import Voice

FORMAT = 'pcm_22050' # Match local tts quality, not top but still good
MODEL = 'eleven_flash_v2_5'#'eleven_monolingual_v1'


class ElevenLabsTTS(TTS):
    def __init__(self, config: Config, full_instance: bool = False):
        super().__init__(config=None)
        self.full_instance = full_instance
        self.config = config
        self.client: AsyncElevenLabs = None

        if self.full_instance:
            request_elevenlabs_connect.addListener(self.setup)
            self.setup()
            on_elevenlabs_test_speak.addListener(self.test_speak)
        
        self.sample_rate = int(FORMAT.split("_")[-1])
        self.bits_per_sample = 16
        self.num_channels = 1

        self.max_chunk_size = 1024*8*8*2*2 # 256kb

        if config.getboolean(section="CACHE", option="enabled"):
            # Caching in general, but for here, it's specific to API results
            cache_dir = config.get(section="CACHE", option="directory", fallback=None)
            if not cache_dir:
                self.cache = Cache()
            else:
                self.cache = Cache(directory=cache_dir)
        else:
            self.cache = None

    @property
    def voices(self) -> dict:
        d = {}
        _voices = run_coroutine_sync(fetch_voices(source='elevenlabs'))
        for v in _voices:
            d.setdefault(f"{v.name} ({v.uid})", v.uid)
        return d

    def setup(self):

        if self.full_instance:
            on_elevenlabs_connect.trigger([False])
        if key := self.config.get(section="ELEVENLABS", option="api_key"):
            try:
                test_client = ElevenLabs(api_key=key)
                # This will cause an exception if invalid api key
                user = test_client.user.get() # TODO : display in settings the amount left in credits in user get or get subscription? Or swap ppl to local when low, or just popup warn?

                self.client = AsyncElevenLabs(api_key=key)
                if self.full_instance:
                    on_elevenlabs_connect.trigger([True])
            except Exception as e:
                logger.warn(f"ElevenLabs Exception: {e}")
                if self.full_instance:
                    on_elevenlabs_connect.trigger([False])


    async def audio_stream_generator(self, text="Hello World!", voice_id: str = None):
        if not voice_id or not self.client:
            return
        
        async def fetch_stream(client, text, voice_id, model, _format):
            output = io.BytesIO()
            async for chunk in client.text_to_speech.convert_as_stream(text=text,
                                                                       voice_id=voice_id,
                                                                       model_id=model,
                                                                       output_format=_format):
                output.write(chunk)
            output.seek(0)
            return output
        return await fetch_stream(self.client, text, voice_id, MODEL, FORMAT)

    async def get_stream(self, text="Hellow world!", voice_id: str = None):
        if not voice_id or not self.client:
            yield None, None
        
        output = await self.audio_stream_generator(text, voice_id)
        
        header = create_wav_header(self.sample_rate, self.bits_per_sample, self.num_channels, len(output.getvalue()))
        chunk_size = min(self.max_chunk_size, len(output.getvalue()))
        chunk = output.read(chunk_size)

        while chunk:
            duration = (len(chunk) / (self.sample_rate * self.num_channels * (self.bits_per_sample // 8)))
            await asyncio.sleep(duration)
            yield (header + chunk, duration)
            chunk = output.read(chunk_size)


    def get_voice_object(self, voice_id: str = "", run_sync_always: bool = False) -> ELVoice | None :
        # Voice by id, will attempt to find it and cache it
        if not voice_id or not self.config.get(section="ELEVENLABS", option="api_key", fallback=None):
            return None

        key = f"11l.voice.{voice_id}"
        v: ELVoice = None
        if self.cache is not None:
            v = self.cache.get(key=key, default=None)
            if v:
                logger.debug(f"Fetched cached preview audio for `{voice_id}`")

        if not v:
            client = ElevenLabs(api_key=self.config.get(section="ELEVENLABS", option="api_key"))
            v = None
            try:
                v = client.voices.get(voice_id)
            except:
                pass
            if v:
                self.cache.set(key=key, expire=self.config.getint(section="CACHE", option="tts_cache_expiry", fallback=7*24*60*60*4*3), value=v)

        if v:
            if run_coroutine_sync:
                run_coroutine_sync(_upsert_voice(name=v.name, uid=v.voice_id, source=SOURCE_11L))
            elif loop := asyncio.get_event_loop():
                asyncio.create_task(_upsert_voice(name=v.name, uid=v.voice_id, source=SOURCE_11L))
            else:
                run_coroutine_sync(_upsert_voice(name=v.name, uid=v.voice_id, source=SOURCE_11L))
        return v


    def test_speak(self, text:str = "Hello there. How are you?", voice_id: str = None):
        if not voice_id or not self.config.get(section="ELEVENLABS", option="api_key", fallback=None):
            return
        # Could use `preview_url` from Voice object, but it is different for each voice, likely best to spend a few credits for consistency and cache it for a long time
        voice_o = self.get_voice_object(voice_id)

        key = f"11l.preview.{voice_id}"
        audio = None
        if self.cache is not None:
            audio_l = self.cache.get(key=key, default=None)
            if audio_l:
                audio = iter(audio_l)
                logger.debug(f"Fetched cached preview audio for `{voice_id}`")
        if not audio:
            try:
                client = ElevenLabs(api_key=self.config.get(section="ELEVENLABS", option="api_key"))
                user = client.user.get() # Trigger bad api key
            except:
                on_elevenlabs_connect.trigger([False]) # needed?
                return
            audio = list(client.generate(text=text, voice=voice_id, model=MODEL))
            self.cache.set(key=key, expire=self.config.getint(section="CACHE", option="tts_cache_expiry", fallback=7*24*60*60*4*3), value=list(audio))
            audio = iter(audio)

        thread = threading.Thread(target=play, args=(audio,))
        thread.daemon = True
        thread.start()

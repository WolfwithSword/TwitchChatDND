import asyncio
import threading
import base64, io, struct
import pyttsx4

from tts.tts import TTS, create_wav_header

from helpers import TCDNDConfig as Config
from helpers.utils import run_coroutine_sync
from helpers.constants import SOURCE_LOCAL
from custom_logger.logger import logger

from data.voices import _upsert_voice, fetch_voices, get_all_voice_ids
from data import Voice


# TODO: For local TTS, there is a slight minor clipping when transitioning between chunks. Mitigated with a large chunk size, need better solution? may be fixed


class LocalTTS(TTS): 
    def __init__(self, config: Config, full_instance: bool = True):
        super().__init__(config=None)
        
        self.sample_rate = 22050 # PyTTS default
        self.bits_per_sample = 16
        self.num_channels = 1

        self.max_chunk_size = 1024*8*8*2*2 # 256kb

        if full_instance:
            engine = pyttsx4.init() 
            db_voice_ids = run_coroutine_sync(get_all_voice_ids(source=SOURCE_LOCAL))
            for v in engine.getProperty('voices'):
                if v.id not in db_voice_ids:
                    run_coroutine_sync(_upsert_voice(name=v.name, uid=v.id, source=SOURCE_LOCAL))

    @property
    def voices(self) -> dict:
        d = {}
        _voices = run_coroutine_sync(fetch_voices(source='local'))
        for v in _voices:
            d.setdefault(f"{v.name}", v.uid)
        return d

    def list_voices(self) -> list:
        friendly_names = list()
        engine = pyttsx4.init() 
        for v in engine.getProperty('voices'):
            n = v.name.split('-')[0].replace("Desktop", "").replace("Microsoft", "").strip()
            friendly_names.append(n)
        return friendly_names

    def get_voice_id_by_friendly_name(self, name: str) -> str:
        if not name:
            return None
        engine = pyttsx4.init() 
        for v in engine.getProperty('voices'):
            n = v.name.split('-')[0].replace("Desktop", "").replace("Microsoft", "").strip()
            if n.lower() == name.lower().strip():
                return v.id

    def voice_list_message(self) -> str:
        voices = self.list_voices()
        return "Local Voices: " + ", ".join(voices)

    def audio_stream_generator(self, text="Hello World!", voice_id: str = None):
        engine = pyttsx4.init() # We are using the fork for x4 as it works with outputting to bytesIO
        output = io.BytesIO()

        if voice_id and voice_id in self.get_voices().values():
            engine.setProperty('voice', voice_id)

        engine.setProperty('rate', 150)  # Speed of speech
        engine.setProperty('volume', 1)  # Volume level (0.0 to 1.0)

        engine.save_to_file(text, output)
        _th = threading.Thread(target=engine.runAndWait)
        _th.daemon = True
        _th.start()
        _th.join()

        output.seek(0)

        return output

    async def get_stream(self, text="Hello World!", voice_id: str = ''):
        output = self.audio_stream_generator(text, voice_id)
        header = create_wav_header(self.sample_rate, self.bits_per_sample, self.num_channels, len(output.getvalue()))
        chunk_size = min(self.max_chunk_size, len(output.getvalue()))
        chunk = output.read(chunk_size)

        while chunk:
            duration = (len(chunk) / (self.sample_rate * self.num_channels * (self.bits_per_sample // 8)))
            await asyncio.sleep(duration)
            yield (header + chunk, duration)
            chunk = output.read(chunk_size)

    def test_speak(self, text:str ="Hello there. How are you?", voice_id: str = None):
        def _run(text, voice_id):
            engine = pyttsx4.init()
            if voice_id in self.voices.values():
                engine.setProperty('voice', voice_id)
            engine.say(text)
            engine.runAndWait()
        thread = threading.Thread(target=_run, args=(text, voice_id))
        thread.daemon = True
        thread.start()

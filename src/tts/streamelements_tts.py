import asyncio
import threading
import io
import requests  # could do aiohttp if needed

from elevenlabs import play
from diskcache import Cache
from pydub import AudioSegment

from tts.tts import TTS

from helpers import TCDNDConfig as Config
from helpers.utils import run_coroutine_sync
from helpers.constants import SOURCE_SE

from custom_logger.logger import logger

from data.voices import bulk_insert_voices, fetch_voices, get_all_voice_ids


class StreamElementsTTS(TTS):
    source_type = SOURCE_SE

    def __init__(self, config: Config, full_instance: bool = True):
        super().__init__(config=None)

        self.config = config
        self.url = "https://api.streamelements.com/kappa/v2/speech?"

        if full_instance:
            db_voice_ids = run_coroutine_sync(get_all_voice_ids(source=self.source_type))
            if not db_voice_ids:

                def _init_values():
                    run_coroutine_sync(bulk_insert_voices(values=[(f"SE {voice}", f"se.{voice}") for voice in se_voices], source=self.source_type))

                thread = threading.Thread(target=_init_values)
                thread.daemon = True
                thread.start()

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
        _voices = run_coroutine_sync(fetch_voices(source=self.source_type))
        for v in _voices:
            d.setdefault(f"{v.name}", v.uid)
        return d

    def voice_list_message(self) -> str:
        return "You can find a list of SE voice_ids here: https://github.com/WolfwithSword/TwitchChatDND/wiki/Integrations#streamelements"

    def get_se_voice(self, voice_id: str) -> str:
        if "se." in voice_id:
            return voice_id.split("se.")[1]
        return ""

    def search_for_voice_by_id(self, uid: str) -> str:
        base_voice = self.get_se_voice(uid)
        if base_voice in se_voices:
            return f"se.{base_voice}"
        return None

    def audio_stream_generator(self, text="Hello World!", voice_id: str | None = None):
        _initial = io.BytesIO()
        output = io.BytesIO()

        res = requests.get(self.url, {"voice": self.get_se_voice(voice_id), "text": text}, timeout=30)
        # Comes back as mp3/id3 instead of wav/riff

        if res.status_code == 200:
            _initial.write(res.content)
        else:
            logger.error(f"Could not request TTS from StreamElements. Error: {res.content}")
        _initial.seek(0)
        audio = AudioSegment.from_file(_initial, format="mp3")
        boosted = audio + self.config.getfloat(section="STREAMELEMENTS", option="boost_db", fallback=6.2)  # dB
        boosted.export(output, format="mp3")
        output.seek(0)
        return output

    async def get_stream(self, text="Hello World!", voice_id: str | None = None):
        output = self.audio_stream_generator(text, voice_id)

        chunk_size = min(self.max_chunk_size, len(output.getvalue()))
        chunk = output.read(chunk_size)

        while chunk:
            duration = len(chunk) / (self.sample_rate * self.num_channels * (self.bits_per_sample // 8))
            await asyncio.sleep(duration)
            yield (chunk, duration)
            chunk = output.read(chunk_size)

    def test_speak(self, text: str = "Hello there. How are you?", voice_id: str | None = None):
        key = f"se.preview.{voice_id}"
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


# To set your voice to one of these, you need to prefix it with 'se.' to get its voice_id. Ex: se.Brian
se_voices = [
    "Brian",
    "Amy",
    "Emma",
    "Geraint",
    "Russell",
    "Nicole",
    "Joey",
    "Justin",
    "Matthew",
    "Ivy",
    "Joanna",
    "Kendra",
    "Kimberly",
    "Salli",
    "Raveena",
    "Zhiyu",
    "Mads",
    "Naja",
    "Ruben",
    "Lotte",
    "Mathieu",
    "Celine",
    "Chantal",
    "Hans",
    "Marlene",
    "Vicki",
    "Aditi",
    "Karl",
    "Dora",
    "Carla",
    "Bianca",
    "Giorgio",
    "Takumi",
    "Mizuki",
    "Seoyeon",
    "Liv",
    "Ewa",
    "Maja",
    "Jacek",
    "Jan",
    "Ricardo",
    "Vitoria",
    "Cristiano",
    "Ines",
    "Carmen",
    "Maxim",
    "Tatyana",
    "Enrique",
    "Conchita",
    "Mia",
    "Miguel",
    "Penelope",
    "Astrid",
    "Filiz",
    "Gwyneth",
    "Linda",
    "Heather",
    "Sean",
    "Hoda",
    "Naayf",
    "Ivan",
    "Herena",
    "Tracy",
    "Danny",
    "Huihui",
    "Yaoyao",
    "Kangkang",
    "HanHan",
    "Zhiwei",
    "Matej",
    "Jakub",
    "Guillaume",
    "Michael",
    "Karsten",
    "Stefanos",
    "Szabolcs",
    "Andika",
    "Heidi",
    "Kalpana",
    "Hemant",
    "Rizwan",
    "Filip",
    "Lado",
    "Valluvar",
    "Pattara",
    "An",
    "en-US-Wavenet-A",
    "en-US-Wavenet-B",
    "en-US-Wavenet-C",
    "en-US-Wavenet-D",
    "en-US-Wavenet-E",
    "en-US-Wavenet-F",
    "en-US-Standard-B",
    "en-US-Standard-C",
    "en-US-Standard-D",
    "en-US-Standard-E",
    "en-GB-Standard-A",
    "en-GB-Standard-B",
    "en-GB-Standard-C",
    "en-GB-Standard-D",
    "en-GB-Wavenet-A",
    "en-GB-Wavenet-B",
    "en-GB-Wavenet-C",
    "en-GB-Wavenet-D",
    "en-AU-Standard-A",
    "en-AU-Standard-B",
    "en-AU-Wavenet-A",
    "en-AU-Wavenet-B",
    "en-AU-Wavenet-C",
    "en-AU-Wavenet-D",
    "en-AU-Standard-C",
    "en-AU-Standard-D",
    "en-IN-Wavenet-A",
    "en-IN-Wavenet-B",
    "en-IN-Wavenet-C",
    "af-ZA-Standard-A",
    "ar-XA-Wavenet-A",
    "ar-XA-Wavenet-B",
    "ar-XA-Wavenet-C",
    "bg-bg-Standard-A",
    "cmn-CN-Wavenet-A",
    "cmn-CN-Wavenet-B",
    "cmn-CN-Wavenet-C",
    "cmn-CN-Wavenet-D",
    "cs-CZ-Wavenet-A",
    "da-DK-Wavenet-A",
    "nl-NL-Standard-A",
    "nl-NL-Wavenet-A",
    "nl-NL-Wavenet-B",
    "nl-NL-Wavenet-C",
    "nl-NL-Wavenet-D",
    "nl-NL-Wavenet-E",
    "fil-PH-Wavenet-A",
    "fi-FI-Wavenet-A",
    "fr-FR-Standard-C",
    "fr-FR-Standard-D",
    "fr-FR-Wavenet-A",
    "fr-FR-Wavenet-B",
    "fr-FR-Wavenet-C",
    "fr-FR-Wavenet-D",
    "fr-CA-Standard-A",
    "fr-CA-Standard-B",
    "fr-CA-Standard-C",
    "fr-CA-Standard-D",
    "de-DE-Standard-A",
    "de-DE-Standard-B",
    "de-DE-Wavenet-A",
    "de-DE-Wavenet-B",
    "de-DE-Wavenet-C",
    "de-DE-Wavenet-D",
    "el-GR-Wavenet-A",
    "hi-IN-Wavenet-A",
    "hi-IN-Wavenet-B",
    "hi-IN-Wavenet-C",
    "hu-HU-Wavenet-A",
    "is-is-Standard-A",
    "id-ID-Wavenet-A",
    "id-ID-Wavenet-B",
    "id-ID-Wavenet-C",
    "it-IT-Standard-A",
    "it-IT-Wavenet-A",
    "it-IT-Wavenet-B",
    "it-IT-Wavenet-C",
    "it-IT-Wavenet-D",
    "ja-JP-Standard-A",
    "ja-JP-Wavenet-A",
    "ja-JP-Wavenet-B",
    "ja-JP-Wavenet-C",
    "ja-JP-Wavenet-D",
    "ko-KR-Standard-A",
    "ko-KR-Wavenet-A",
    "lv-lv-Standard-A",
    "nb-no-Wavenet-E",
    "nb-no-Wavenet-A",
    "nb-no-Wavenet-B",
    "nb-no-Wavenet-C",
    "nb-no-Wavenet-D",
    "pl-PL-Wavenet-A",
    "pl-PL-Wavenet-B",
    "pl-PL-Wavenet-C",
    "pl-PL-Wavenet-D",
    "pt-PT-Wavenet-A",
    "pt-PT-Wavenet-B",
    "pt-PT-Wavenet-C",
    "pt-PT-Wavenet-D",
    "pt-BR-Standard-A",
    "ru-RU-Wavenet-A",
    "ru-RU-Wavenet-B",
    "ru-RU-Wavenet-C",
    "ru-RU-Wavenet-D",
    "sr-rs-Standard-A",
    "sk-SK-Wavenet-A",
    "es-ES-Standard-A",
    "sv-SE-Standard-A",
    "tr-TR-Standard-A",
    "tr-TR-Wavenet-A",
    "tr-TR-Wavenet-B",
    "tr-TR-Wavenet-C",
    "tr-TR-Wavenet-D",
    "tr-TR-Wavenet-E",
    "uk-UA-Wavenet-A",
    "vi-VN-Wavenet-A",
    "vi-VN-Wavenet-B",
    "vi-VN-Wavenet-C",
    "vi-VN-Wavenet-D",
]

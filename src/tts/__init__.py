from tts.local_tts import LocalTTS
from tts.elevenlabs_tts import ElevenLabsTTS
from tts.streamelements_tts import StreamElementsTTS
from tts.tts import TTS
from helpers.constants import SOURCES
from helpers import TCDNDConfig as Config

__all__ = ["SOURCES", "LocalTTS", "ElevenLabsTTS", "StreamElementsTTS", "initialize_tts", "tts_instances", 'TTS']

tts_instances = {}


def initialize_tts(config: Config):
    # Initialize once globally and import instances where needed
    for tts_cls in [LocalTTS, ElevenLabsTTS, StreamElementsTTS]:
        if tts_cls.source_type in SOURCES and tts_cls.source_type not in tts_instances:
            tts_instances[tts_cls.source_type] = tts_cls(config, True)

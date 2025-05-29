from tts.local_tts import LocalTTS
from tts.elevenlabs_tts import ElevenLabsTTS
from tts.chatterbox_tts import ChatterBoxTTS

from helpers import TCDNDConfig as Config
from helpers.constants import SOURCE_11L, SOURCE_LOCAL, SOURCE_CHATTER

__all__ = ["LocalTTS", "ElevenLabsTTS", "ChatterBoxTTS", "initialize", "instances"]

instances = {}

def initialize_tts(source: str, config: Config):
    if source not in instances:
        if source == SOURCE_11L:
            instances[source] = ElevenLabsTTS(config, True)
        elif source == SOURCE_CHATTER:
            instances[source] = ChatterBoxTTS(config, True)
        elif source == SOURCE_LOCAL:
            instances[source] = LocalTTS(config, True)
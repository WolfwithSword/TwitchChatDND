from logging import getLogger
from functools import lru_cache

from tts.local_tts import LocalTTS
from tts.elevenlabs_tts import ElevenLabsTTS
from tts.streamelements_tts import StreamElementsTTS
from tts.tts import TTS
from helpers.constants import TTS_SOURCE

logger = getLogger("ChatDND")

__all__ = ["LocalTTS", "ElevenLabsTTS", "StreamElementsTTS", 'TTS', "get_tts"]

_tts_store_ = {}
_tts_classes_ = [LocalTTS, ElevenLabsTTS, StreamElementsTTS]

# def initialize_tts():
#     # Initialize once globally and import instances where needed
#     for tts_cls in [LocalTTS, ElevenLabsTTS, StreamElementsTTS]:
#         if tts_cls.source_type in SOURCES and tts_cls.source_type not in tts_instances:
#             tts_instances[tts_cls.source_type] = tts_cls()

@lru_cache(maxsize=None)
def get_tts(name: TTS_SOURCE) -> LocalTTS | ElevenLabsTTS | StreamElementsTTS:
    if not name:
        return None
    if name in _tts_store_:
        return  _tts_store_.get(name)
    for cls in _tts_classes_:
        if cls.source_type == name:
            tts = cls()
            _tts_store_[name] = tts
            return tts
    return None

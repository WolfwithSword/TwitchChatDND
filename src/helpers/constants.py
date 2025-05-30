
# Keep always as lowercase
from enum import Enum


class TTS_SOURCE(Enum): #pylint: disable=invalid-name
    SOURCE_LOCAL = "local"
    SOURCE_11L = "elevenlabs"
    SOURCE_SE = 'streamelements'

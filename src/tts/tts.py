from logging import getLogger
import struct
from helpers.constants import TTS_SOURCE

logger = getLogger("ChatDND")


def create_wav_header(sample_rate, bits_per_sample, num_channels, data_size):
    # WAV File header
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",  # ChunkID
        36 + data_size,  # ChunkSize
        b"WAVE",  # Format
        b"fmt ",  # Subchunk1ID
        16,  # Subchunk1Size
        1,  # AudioFormat (PCM)
        num_channels,  # NumChannels
        sample_rate,  # SampleRate
        byte_rate,  # ByteRate
        block_align,  # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",  # Subchunk2ID
        data_size,  # Subchunk2Size
    )
    return header


class TTS:
    source_type: TTS_SOURCE
    voices: dict = dict()
    sample_rate = 22050
    bits_per_sample = 16
    num_channels = 1
    max_chunk_size = 1024 * 8 * 8 * 2 * 2  # 256kb

    def __init__(self):
        logger.debug(f"TTS Instance created of type: {self.source_type}")

    def get_voices(self) -> dict:
        return self.voices

    async def get_stream(self):
        yield (None, 0)

    def list_voices(self) -> list:
        return []

    def voice_list_message(self) -> str:
        return "Available Voices: " + ", ".join(self.list_voices())

from helpers import TCDNDConfig as Config
from custom_logger.logger import logger
import base64, io, struct
from helpers.utils import run_coroutine_sync

def create_wav_header(sample_rate, bits_per_sample, num_channels, data_size):
    # WAV File header
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8

    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',  # ChunkID
        36 + data_size,  # ChunkSize
        b'WAVE',  # Format
        b'fmt ',  # Subchunk1ID
        16,  # Subchunk1Size
        1,  # AudioFormat (PCM)
        num_channels,  # NumChannels
        sample_rate,  # SampleRate
        byte_rate,  # ByteRate
        block_align,  # BlockAlign
        bits_per_sample,  # BitsPerSample
        b'data',  # Subchunk2ID
        data_size,  # Subchunk2Size
    )
    return header


class TTS():
    
    voices: dict = dict()
    
    def __init__(self, config: Config):
        self.config = config

    def get_voices(self) -> dict:
        return self.voices
    
    async def get_stream(self):
        yield (None, 0)
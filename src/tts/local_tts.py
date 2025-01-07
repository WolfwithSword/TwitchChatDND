import asyncio
import base64, io, struct
import pyttsx4

from helpers import TCDNDConfig as Config
from custom_logger.logger import logger


# TODO: For local TTS, there is a slight minor clipping when transitioning between chunks. Mitigated with a large chunk size, need better solution

# May be needed by cloud tts as well? so prob candidate to move
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

class LocalTTS(): # TODO Refactor with some inheritance from a TTS class, so we can abstract both Local and Cloud TTS later on
    def __init__(self, config: Config):
        self.config = config
        
        self.sample_rate = 22050 # PyTTS default
        self.bits_per_sample = 16
        self.num_channels = 1

        self.max_chunk_size = 1024*8*8*2 # 128kb

    def audio_stream_generator(self, text="Hello World!"):
        engine = pyttsx4.init() # We are using the fork for x4 as it works with outputting to bytesIO
        output = io.BytesIO()

        # TODO Uses default tts on at the moment. Can configure later
        engine.setProperty('rate', 150)  # Speed of speech
        engine.setProperty('volume', 1)  # Volume level (0.0 to 1.0)

        engine.save_to_file(text, output)
        engine.runAndWait()
        output.seek(0)

        return output

    async def get_stream(self, text="Hello World!"):
        output = self.audio_stream_generator(text)
        header = create_wav_header(self.sample_rate, self.bits_per_sample, self.num_channels, len(output.getvalue()))
        chunk_size = min(self.max_chunk_size, len(output.getvalue()))
        chunk = output.read(chunk_size)

        while chunk:
            await asyncio.sleep((len(chunk) / (self.sample_rate * self.num_channels * (self.bits_per_sample // 8))))
            yield header + chunk
            chunk = output.read(chunk_size)
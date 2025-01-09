from helpers import TCDNDConfig as Config
from custom_logger.logger import logger

class TTS():
    
    voices: dict = dict()
    
    def __init__(self, config: Config):
        self.config = config

    def get_voices(self) -> dict:
        return self.voices
import configparser
import base64

# ID is fine to ship
_client_id = base64.b64decode("dXp4NXFiOXNzZXl0dGtvZXF5cXdydmthOGdic3Br").decode('utf-8')

class TCDNDConfig(configparser.ConfigParser):

    def __init__(self):
        super().__init__()
        self.path = "./config.ini"

    def setup(self, path: str):
        self.path = path
        self.read(path)

        # Init config.ini file
        needs_init = False
        if not self.has_section("BOT"):
            needs_init = True
            self.add_section("BOT")
        if not self.get(section="BOT", option="prefix", fallback=None):
            needs_init = True
            self.set(section="BOT", option="prefix", value="!")
        if not self.get(section="BOT", option="speak_command", fallback=None):
            needs_init = True
            self.set(section="BOT", option="speak_command", value="say")
        if not self.get(section="BOT", option="join_command", fallback=None):
            needs_init = True
            self.set(section="BOT", option="join_command", value="join")
        if not self.get(section="BOT", option="voices_command", fallback=None):
            needs_init = True
            self.set(section="BOT", option="voices_command", value="voices")
        if not self.get(section="BOT", option="voice_command", fallback=None):
            needs_init = True
            self.set(section="BOT", option="voice_command", value="voice")

        if not self.has_section("SERVER"):
            needs_init = True
            self.add_section("SERVER")
        if not self.get(section="SERVER", option="port", fallback=None):
            needs_init = True
            self.set(section="SERVER", option="port", value=str(5000))

        if not self.has_section("CACHE"):
            needs_init = True
            self.add_section("CACHE")
        if not self.has_option(section="CACHE", option="enabled"):
            needs_init = True
            self.set(section="CACHE", option="enabled", value='true')
        if not self.has_option(section="CACHE", option="cache_expiry"):
            needs_init = True
            self.set(section="CACHE", option="cache_expiry", value=str(7*24*60*60))
        if not self.has_option(section="CACHE", option="tts_cache_expiry"):
            needs_init = True
            self.set(section="CACHE", option="tts_cache_expiry", value=str(7*24*60*60*4*3))
        
        if not self.has_section("TWITCH"):
            needs_init = True
            self.add_section("TWITCH")
        if not self.has_option(section="TWITCH", option="channel"):
            needs_init = True
            self.set(section="TWITCH", option="channel", value="")

        if not self.has_section("DND"):
            needs_init = True
            self.add_section("DND")
        if not self.has_option(section="DND", option="party_size"):
            needs_init = True
            self.set(section="DND", option="party_size", value=str(4))

        if not self.has_section("ELEVENLABS"):
            needs_init = True
            self.add_section("ELEVENLABS")
        if not self.has_option(section="ELEVENLABS", option="api_key"):
            needs_init = True
            self.set(section="ELEVENLABS", option="api_key", value='')

        if needs_init:
            self.write_updates()

    @property
    def twitch_auth(self) -> tuple[str, str]:
        return _client_id.strip()

    @property
    def cache_enabled(self) -> bool:
        return self.getboolean(section='CACHE', option='enabled', fallback=False)

    def write_updates(self):
        with open(self.path, 'w') as configfile:
            self.write(configfile)
        self.read(self.path)

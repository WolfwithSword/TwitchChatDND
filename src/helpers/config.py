import configparser
import base64

# ID is fine to ship
_client_id = base64.b64decode("dXp4NXFiOXNzZXl0dGtvZXF5cXdydmthOGdic3Br").decode("utf-8")


class TCDNDConfig(configparser.ConfigParser):

    def __init__(self):
        super().__init__()
        self.path = "./config.ini"

    def _setup_section(self, section: str) -> bool:
        _needs_init = False
        if not self.has_section(section):
            _needs_init = True
            self.add_section(section)
        return _needs_init

    def _setup_option(self, section: str, option: str, value: str) -> bool:
        _needs_init = False
        if not self.get(section=section, option=option, fallback=None):
            _needs_init = True
            self.set(section=section, option=option, value=str(value))
        return _needs_init

    def setup(self, path: str):
        self.path = path
        self.read(path)

        _defaults = {
            "BOT": {
                "prefix": "!",
                "speak_command": "say",
                "join_command": "join",
                "voices_command": "voices",
                "voice_command": "voice",
                "help_command": "dndhelp",
                "voice_user_cooldown": 10,
                "voices_user_cooldown": 15,
                "voices_global_cooldown": 10,
                "speak_global_cooldown": 1,
                "speak_user_cooldown": 10,
                "join_user_cooldown": 30,
                "help_global_cooldown": 30,
            },
            "SERVER": {"port": "5000"},
            "CACHE": {
                "enabled": "true",
                "cache_expiry": 7 * 24 * 60 * 60,  # 1 week
                "tts_cache_expiry": 7 * 24 * 60 * 60 * 4 * 3,  # 3 months
                "pfp_cache_expiry": 7 * 24 * 60 * 60 * 2,  # 2 weeks
            },
            "DND": {"party_size": 4},
            "ELEVENLABS": {"api_key": "", "usage_warning": 500},
            "STREAMELEMENTS": {"boost_db": 6.8},
        }

        # Init config.ini file
        needs_init = False

        for section in list(_defaults.keys()):
            needs_init = needs_init or self._setup_section(section)
            for key, value in _defaults[section].items():
                needs_init = needs_init or self._setup_option(section=section, option=key, value=value)

        if needs_init:
            self.write_updates()

    @property
    def twitch_auth(self) -> tuple[str, str]:
        return _client_id.strip()

    @property
    def cache_enabled(self) -> bool:
        return self.getboolean(section="CACHE", option="enabled", fallback=False)

    def write_updates(self):
        with open(self.path, "w", encoding="utf-8") as configfile:
            self.write(configfile)
        self.read(self.path)

    def get_command_cooldown(self, command: str, scope: str) -> int:
        if scope not in ["user", "global"]:
            return 0
        if self.has_option(section="BOT", option=f"{command}_{scope}_cooldown".lower()):
            return self.getint(section="BOT", option=f"{command}_{scope}_cooldown".lower(), fallback=0)
        return 0

import configparser


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
        
        if not self.has_section("TWITCH"):
            needs_init = True
            self.add_section("TWITCH")
        if not self.has_option(section="TWITCH", option="channel"):
            needs_init = True
            self.set(section="TWITCH", option="channel", value="")
        if not self.has_option(section="TWITCH", option="client_id"):
            needs_init = True
            self.set(section="TWITCH", option="client_id", value="")
        if not self.has_option(section="TWITCH", option="client_secret"):
            needs_init = True
            self.set(section="TWITCH", option="client_secret", value="")

        if not self.has_section("DND"):
            needs_init = True
            self.add_section("DND")
        if not self.has_option(section="DND", option="party_size"):
            needs_init = True
            self.set(section="DND", option="party_size", value=str(4))

        if needs_init:
            self.write_updates()

    @property
    def twitch_auth(self) -> tuple[str, str]:
        client_id = self.get(section='TWITCH', option='client_id', fallback='')
        client_secret = self.get(section='TWITCH', option='client_secret', fallback='')
        if client_id == '' or client_secret == '':
            return None, None
        return client_id.strip(), client_secret.strip()

    @property
    def cache_enabled(self) -> bool:
        return self.getboolean(section='CACHE', option='enabled', fallback=False)

    def write_updates(self):
        with open(self.path, 'w') as configfile:
            self.write(configfile)
        self.read(self.path)

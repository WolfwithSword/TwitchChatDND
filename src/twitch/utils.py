from typing import List
import webbrowser

from twitchAPI.helper import first
from twitchAPI.object.api import TwitchUser
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticationStorageHelper, CodeFlow
from twitchAPI.type import AuthScope

from diskcache import Cache

from helpers import TCDNDConfig as Config
from custom_logger.logger import logger

from chatdnd.events.twitchutils_events import twitchutils_twitch_on_connect_event
from chatdnd.events.ui_events import ui_settings_twitch_auth_update_event


class TwitchUtils:

    def __init__(self, config: Config, cache_dir: str = ""):
        self.twitch: Twitch = None
        self.config: Config = config
        self.channel: TwitchUser = None

        if config.getboolean(section="CACHE", option="enabled"):
            # Caching in general, but for here, it's specific to API results
            if not cache_dir:
                self.cache = Cache()
            else:
                self.cache = Cache(directory=cache_dir)
        else:
            self.cache = None

        ui_settings_twitch_auth_update_event.addListener(self.start)

    async def _token_gen(self, twitch: Twitch, target_scope: List[AuthScope]) -> (str, str):
        code_flow = CodeFlow(twitch, target_scope)
        # Local callback didnt work, but CodeFlow does. Will open browser for it, then store locally due to StorageHelper
        code, url = await code_flow.get_code()
        webbrowser.open(url, new=0, autoraise=True)
        token, refresh = await code_flow.wait_for_auth_complete()
        return token, refresh

    async def start(self):
        self.twitch = None
        scopes = [
            AuthScope.CHAT_READ,
            AuthScope.CHAT_EDIT,
        ]  # TODO may need more as time goes on
        try:
            self.twitch = await Twitch(app_id=self.config.twitch_auth, authenticate_app=False)
            helper = UserAuthenticationStorageHelper(self.twitch, scopes, auth_generator_func=self._token_gen)
            await helper.bind()
        except Exception as e:
            logger.error(e)
            twitchutils_twitch_on_connect_event.trigger([False, None])
            raise
        logger.info("Twitch connected")
        twitchutils_twitch_on_connect_event.trigger([True, self])

        async for user_info in self.twitch.get_users():
            self.channel = user_info
            break

    async def get_user_by_name(self, username: str):
        username = username.lower()
        key = f"{username}.twitch.user"
        if self.cache is not None:
            user = self.cache.get(key=key, default=None)
            if user:
                logger.debug(f"Fetched twitch user `{username}`")
                return user

        try:
            user = await first(self.twitch.get_users(logins=[username]))
        except Exception as e:
            logger.warning(f"Exception with username {username}, {e}")
            user = None
        if user and user.display_name.lower() == username.lower():
            if self.cache is not None:
                self.cache.set(
                    key=key,
                    expire=self.config.getint(
                        section="CACHE",
                        option="cache_expiry",
                        fallback=7 * 24 * 60 * 60,
                    ),
                    value=user,
                )
            logger.debug(f"Fetched twitch user `{username}`")
            return user
        return None

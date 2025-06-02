from typing import List, Tuple
import webbrowser

from twitchAPI.helper import first
from twitchAPI.object.api import TwitchUser
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticationStorageHelper, CodeFlow
from twitchAPI.type import AuthScope

from data.member import Member
from custom_logger.logger import logger

from helpers.utils import try_get_cache
from helpers.instance_manager import get_config

from chatdnd.events.twitchutils_events import twitchutils_twitch_on_connect_event
from chatdnd.events.ui_events import ui_settings_twitch_auth_update_event, ui_refresh_user, ui_request_member_refresh, ui_request_floating_notif
from ui.widgets.CTkFloatingNotifications.notification_type import NotifyType


class TwitchUtils:

    def __init__(self):
        self.twitch: Twitch = None
        self.channel: TwitchUser = None

        ui_settings_twitch_auth_update_event.addListener(self.start)
        ui_request_member_refresh.addListener(self.refresh_user_by_member)

    async def _token_gen(self, twitch: Twitch, target_scope: List[AuthScope]) -> Tuple[str, str]:
        code_flow = CodeFlow(twitch, target_scope)
        # Local callback didnt work, but CodeFlow does. Will open browser for it, then store locally due to StorageHelper
        code, url = await code_flow.get_code()
        msg = f"Authorizing with Twitch. Verify code matches: {code}"
        ui_request_floating_notif.trigger(
            [
                msg,
                NotifyType.INFO,
                {"duration": 180000, "name": "twitch_auth"},
            ]
        )
        webbrowser.open(url, new=0, autoraise=True)
        token, refresh = await code_flow.wait_for_auth_complete()
        return token, refresh


    async def on_exit(self):
        if self.twitch:
            await self.twitch.close()
            self.twitch = None

    async def start(self):
        await self.on_exit()
        self.twitch = None
        scopes = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT, AuthScope.MODERATOR_MANAGE_ANNOUNCEMENTS]  # TODO may need more as time goes on
        config = get_config("default")
        try:
            self.twitch = await Twitch(app_id=config.twitch_auth, authenticate_app=False)
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

    async def refresh_user_by_member(self, member: Member):
        user = await self.get_user_by_name(username=member.name, skip_cache=True)
        if not user:
            return
        ui_refresh_user.trigger([user])

    async def get_user_by_name(self, username: str, skip_cache: bool = False):
        username = username.lower()
        key = f"{username}.twitch.user"
        config = get_config("default")
        cache = try_get_cache("default")
        if not skip_cache and cache:
            user = cache.get(key=key, default=None)
            if user:
                logger.debug(f"Fetched twitch user `{username}`")
                return user

        try:
            user = await first(self.twitch.get_users(logins=[username]))
        except Exception as e:
            logger.warning(f"Exception with username {username}, {e}")
            user = None
        if user and user.display_name.lower() == username.lower():
            if cache:
                cache.set(
                    key=key,
                    expire=config.getint(
                        section="CACHE",
                        option="cache_expiry",
                        fallback=7 * 24 * 60 * 60,
                    ),
                    value=user,
                )
            logger.debug(f"Fetched twitch user `{username}`")
            return user
        return None

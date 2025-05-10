import asyncio
import datetime
from twitchAPI.chat import Chat, ChatCommand, EventData, Twitch
from twitchAPI.chat.middleware import (
    UserRestriction,
    ChannelCommandCooldown,
    ChannelUserCommandCooldown,
)
from twitchAPI.object.api import TwitchUser
from twitchAPI.type import ChatEvent

from twitch.utils import TwitchUtils

from data.member import create_or_get_member, fetch_member, update_tts

from custom_logger.logger import logger

from helpers import TCDNDConfig as Config
from helpers.constants import SOURCE_11L, SOURCE_LOCAL

from chatdnd import SessionManager
from chatdnd.events.ui_events import (
    ui_settings_bot_settings_update_event,
    ui_settings_twitch_channel_update_event,
)

from chatdnd.events.chat_events import (
    chat_on_session_open,
    chat_on_session_start,
    chat_on_session_end,
    chat_on_channel_fetch,
    chat_bot_on_connect,
    chat_say_command,
    chat_on_join_queue,
    chat_force_party_start_setup,
)
from chatdnd.events.twitchutils_events import twitchutils_twitch_on_connect_event

from chatdnd.events.session_events import on_active_party_update

from tts import ElevenLabsTTS, LocalTTS


class ChatController:
    def __init__(self, session_mgr: SessionManager, config: Config):
        self.twitch_utils: TwitchUtils = None
        self.twitch: Twitch = None
        self.config: Config = config
        self.chat: Chat = None

        self.session_mgr = session_mgr
        self.command_list = {}

        ui_settings_twitch_channel_update_event.addListener(self.start)
        twitchutils_twitch_on_connect_event.addListener(self.start)
        on_active_party_update.addListener(self._update_say_cmd)
        chat_force_party_start_setup.addListener(self._session_start_actions)

    async def start(self, status: bool = None, twitch_utils: TwitchUtils = None, wait_tries: int = 5):
        if not twitch_utils:
            raise Exception("Twitch instance is not instantiated")

        self.twitch_utils = twitch_utils
        for i in range(wait_tries):
            await asyncio.sleep(i + 1)
            if self.twitch_utils.twitch:
                break

        self.twitch = self.twitch_utils.twitch

        if not self.twitch:
            raise Exception("Twitch instance is not instantiated")

        if not self.twitch_utils.channel:
            logger.error(f"Chat channel not found")
            chat_on_channel_fetch.trigger([False])
            raise Exception("Channel not found")
        chat_on_channel_fetch.trigger([True])
        chat_bot_on_connect.trigger([False])
        self.chat = await Chat(self.twitch)
        self.chat.register_event(ChatEvent.READY, self._on_ready)

        self.chat.set_prefix(self.config.get(section="BOT", option="prefix", fallback="!"))

        self.command_list["join"] = self.config.get(section="BOT", option="join_command")
        self.command_list["say"] = self.config.get(section="BOT", option="speak_command")
        self.command_list["voices"] = self.config.get(section="BOT", option="voices_command")
        self.command_list["voice"] = self.config.get(section="BOT", option="voice_command")

        self.command_list["help"] = self.config.get(section="BOT", option="help_command")

        self.chat.register_command(
            self.command_list["help"],
            self._send_help_cmd,
            command_middleware=[ChannelCommandCooldown(self.config.get_command_cooldown("help", "global"))],
        )

        self.chat.register_command(
            self.command_list["voices"],
            self._get_voices,
            command_middleware=[
                ChannelCommandCooldown(self.config.get_command_cooldown("voices", "global")),
                ChannelUserCommandCooldown(self.config.get_command_cooldown("voices", "user")),
            ],
        )
        self.chat.register_command(
            self.command_list["voice"],
            self._set_voice,
            command_middleware=[ChannelUserCommandCooldown(self.config.get_command_cooldown("voice", "user"))],
        )

        ui_settings_bot_settings_update_event.addListener(self.update_bot_settings)

        self.chat.start()
        chat_bot_on_connect.trigger([self.chat.is_connected()])

    def update_bot_settings(self):
        if not self.chat:
            return
        self.chat.set_prefix(self.config.get(section="BOT", option="prefix").strip()[0])
        if self.chat.unregister_command(self.command_list["join"]):
            self.command_list["join"] = self.config.get(section="BOT", option="join_command")
            self.chat.register_command(
                self.command_list["join"],
                self._add_user_to_queue,
                command_middleware=[ChannelUserCommandCooldown(self.config.get_command_cooldown("join", "user"))],
            )

        self._update_say_cmd()

        if self.chat.unregister_command(self.command_list["voices"]):
            self.command_list["voices"] = self.config.get(section="BOT", option="voices_command")
            self.chat.register_command(
                self.command_list["voices"],
                self._get_voices,
                command_middleware=[
                    ChannelCommandCooldown(self.config.get_command_cooldown("voices", "global")),
                    ChannelUserCommandCooldown(self.config.get_command_cooldown("voices", "user")),
                ],
            )
        if self.chat.unregister_command(self.command_list["voice"]):
            self.command_list["voice"] = self.config.get(section="BOT", option="voice_command")
            self.chat.register_command(
                self.command_list["voice"],
                self._set_voice,
                command_middleware=[ChannelUserCommandCooldown(self.config.get_command_cooldown("voice", "user"))],
            )
        if self.chat.unregister_command(self.command_list["help"]):
            self.command_list["help"] = self.config.get(section="BOT", option="help_command")
            self.chat.register_command(
                self.command_list["help"],
                self._send_help_cmd,
                command_middleware=[ChannelCommandCooldown(self.config.get_command_cooldown("help", "global"))],
            )

    def _update_say_cmd(self):
        if self.chat.unregister_command(self.command_list["say"]):
            self.command_list["say"] = self.config.get(section="BOT", option="speak_command")
            self.chat.register_command(
                self.command_list["say"],
                self._say,
                command_middleware=[
                    UserRestriction(allowed_users=[x.name for x in self.session_mgr.session.party]),
                    ChannelCommandCooldown(self.config.get_command_cooldown("speak", "global")),
                    ChannelUserCommandCooldown(self.config.get_command_cooldown("speak", "user")),
                ],
            )

    def stop(self):
        if self.chat:
            self.chat.stop()

    async def _on_ready(self, ready_event: EventData):
        # Cannot put async or sync event triggers in this, as they are in different threads
        logger.info("Bot is ready")
        self.send_message(text="Chat DnD is now active! ⚔️🐉")
        await ready_event.chat.join_room(self.twitch_utils.channel.display_name)  # or .login?

    def send_message(self, text: str, as_announcement: bool = False):
        logger.debug(f"Sending chat msg: {text}")
        if as_announcement:
            asyncio.run_coroutine_threadsafe(
                self.twitch.send_chat_announcement(self.twitch_utils.channel.id, self.twitch_utils.channel.id, text),
                asyncio.get_event_loop(),
            )
        else:
            asyncio.run_coroutine_threadsafe(
                self.chat.send_message(text=text, room=self.twitch_utils.channel.display_name),
                asyncio.get_event_loop(),
            )

    def open_session(self):
        if not self.chat:
            return
        if self.session_mgr:
            self.session_mgr.end()
        self.session_mgr.open()
        self.chat.unregister_command(self.command_list["say"])
        self.chat.register_command(
            self.command_list["join"],
            self._add_user_to_queue,
            command_middleware=[ChannelUserCommandCooldown(self.config.get_command_cooldown("join", "user"))],
        )
        self.send_message(f"Session started! Type {self.chat._prefix}{self.command_list['join']} to queue for the adventuring party", True)
        chat_on_session_open.trigger()

    def _session_start_actions(self):
        self.chat.unregister_command(self.command_list["join"])
        party = [x.name for x in self.session_mgr.session.party]
        self.chat.register_command(
            self.command_list["say"],
            self._say,
            command_middleware=[
                UserRestriction(allowed_users=[x.name for x in self.session_mgr.session.party]),
                ChannelCommandCooldown(self.config.get_command_cooldown("speak", "global")),
                ChannelUserCommandCooldown(self.config.get_command_cooldown("speak", "user")),
            ],
        )

        self.send_message(f"Say welcome to our party members: {", ".join(party)}")
        self.send_message(f"Party members, type {self.chat._prefix}{self.command_list['say']} <msg> to have it spoken via TTS")
        chat_on_session_start.trigger()

    def start_session(self, party_size) -> bool:
        if self.session_mgr.start_session(party_size=party_size):  # config
            self._session_start_actions()
            return True
        else:
            self.send_message(
                f"Not enough party members in the queue! Type {self.chat._prefix}{self.command_list['join']}  to join "
                f"({len(self.session_mgr.session.queue)}/{party_size})"
            )
            return False

    def end_session(self):
        if self.session_mgr:
            self.session_mgr.end()
        self.chat.unregister_command(self.command_list["say"])
        self.chat.unregister_command(self.command_list["join"])
        chat_on_session_end.trigger()

    async def _add_user_to_queue(self, cmd: ChatCommand):
        user: TwitchUser = await self.twitch_utils.get_user_by_name(username=cmd.user.name)
        if not user:
            return
        # TODO idea, provide other stats like vip/mod/status/badges? Can always fetch from twitchAPI especially since we cache for a week, aka no risk
        # TODO we also want a default pfp perhaps if non exists
        member = await create_or_get_member(name=cmd.user.display_name, pfp_url=user.profile_image_url)
        if member not in self.session_mgr.session.queue:
            if (member.time_since_last_session and
                datetime.datetime.now() - datetime.timedelta(minutes=10) < member.time_since_last_session):
                await cmd.reply(f"{member.name} was in a session too recently!")
                return
            await cmd.reply(f"{member.name} added to queue")
            chat_on_join_queue.trigger([cmd.user.name])
        else:
            await cmd.reply(f"{member.name} already in the queue")
            return
        self.session_mgr.join_queue(member)

    async def _say(self, cmd: ChatCommand):
        await asyncio.sleep(0.1)
        if cmd.parameter:
            # Event trigger *does* work here
            member = await fetch_member(cmd.user.name.lower())
            chat_say_command.trigger([member, cmd.parameter])

    async def _send_help_cmd(self, cmd: ChatCommand):
        await cmd.reply("Commands: https://github.com/WolfwithSword/TwitchChatDND/wiki/Commands")

    async def _get_voices(self, cmd: ChatCommand):
        param = cmd.parameter
        if not param or param.upper().strip() not in [
            SOURCE_LOCAL.upper(),
            "11L",
            SOURCE_11L.upper(),
        ]:
            await cmd.reply(
                f"@{cmd.user.display_name} available TTS types are 'local', '11L'. Try {self.chat._prefix}{self.command_list['voices']} <type>"
            )
            return
        param = param.upper().strip()
        msg = ""
        if param == SOURCE_LOCAL.upper():
            tts = LocalTTS(self.config, False)
            msg = tts.voice_list_message()
        elif param in [SOURCE_11L.upper(), "11L"]:
            msg = ElevenLabsTTS.voices_messages()
        if not msg:
            return
        await cmd.reply(msg)

    async def _set_voice(self, cmd: ChatCommand):
        param = cmd.parameter
        if not param or not param.strip():
            await cmd.reply(
                f"@{cmd.user.display_name} Please specify a voice to set to. Find voices using "
                f"{self.chat._prefix}{self.command_list['voices']} <type>"
            )
            return
        param = param.strip()
        voice_id = ""

        # Try each TTS
        if not voice_id:
            tts = LocalTTS(self.config, False)
            voice_id = tts.get_voice_id_by_friendly_name(param)

        if not voice_id:
            tts = ElevenLabsTTS(self.config, False)
            voice = tts.search_for_voice_by_id(param)
            if voice:
                voice_id = voice.voice_id

        msg = ""

        if voice_id:
            user: TwitchUser = await self.twitch_utils.get_user_by_name(username=cmd.user.name)
            if user:
                member = await create_or_get_member(name=cmd.user.display_name, pfp_url=user.profile_image_url)
                await update_tts(member, voice_id)
                msg = f"@{cmd.user.display_name} Successfully set TTS voice!"
            else:
                msg = f"@{cmd.user.display_name} Error setting TTS voice!"
        else:
            msg = f"@{cmd.user.display_name} Could not set TTS voice. Voice not available or not found."
        await cmd.reply(msg)

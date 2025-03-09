import asyncio
from twitchAPI.chat import Chat, ChatCommand, EventData
from twitchAPI.chat.middleware import UserRestriction, ChannelCommandCooldown, ChannelUserCommandCooldown
from twitchAPI.object.api import TwitchUser
from twitchAPI.type import ChatEvent

from twitch.utils import TwitchUtils

from data import Member
from data.member import create_or_get_member, fetch_member, update_tts
from chatdnd import SessionManager

from custom_logger.logger import logger

from helpers import TCDNDConfig as Config
from helpers import Event
from helpers.constants import SOURCE_11L, SOURCE_LOCAL

from chatdnd.events.ui_events import ui_settings_bot_settings_update_event, ui_settings_twitch_channel_update_event
from chatdnd.events.chat_events import *
from chatdnd.events.twitchutils_events import twitchutils_twitch_on_connect_event

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


    async def start(self, status: bool=None, twitch_utils: TwitchUtils=None, wait_tries:int = 5):
        if not twitch_utils:
            raise Exception("Twitch instance is not instantiated")

        self.twitch_utils = twitch_utils
        for i in range(wait_tries):
            await asyncio.sleep(i+1)
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

        self.command_list['join'] = self.config.get(section="BOT", option="join_command")
        self.command_list['say'] = self.config.get(section="BOT", option="speak_command")
        self.command_list['voices'] = self.config.get(section="BOT", option="voices_command")
        self.command_list['voice'] = self.config.get(section="BOT", option="voice_command")

        self.chat.register_command(self.command_list['voices'], 
            self._get_voices, command_middleware=[ChannelCommandCooldown(10),
                                            ChannelUserCommandCooldown(15) ])
        self.chat.register_command(self.command_list['voice'], 
            self._set_voice, command_middleware=[ChannelUserCommandCooldown(10)])

        ui_settings_bot_settings_update_event.addListener(self.update_bot_settings)

        self.chat.start()
        chat_bot_on_connect.trigger([self.chat.is_connected()])
        

    def update_bot_settings(self):
        if not self.chat:
            return
        self.chat.set_prefix(self.config.get(section="BOT", option="prefix").strip()[0])
        if self.chat.unregister_command(self.command_list['join']):
            self.command_list['join'] = self.config.get(section="BOT", option="join_command")
            self.chat.register_command(self.command_list['join'], self._add_user_to_queue, command_middleware=[ChannelUserCommandCooldown(30)])
        if self.chat.unregister_command(self.command_list['say']):
            self.command_list['say'] = self.config.get(section="BOT", option="speak_command")
            self.chat.register_command(self.command_list['say'], 
                self._say, command_middleware=[UserRestriction(allowed_users=[x.name for x in self.session_mgr.session.party]),
                                          ChannelCommandCooldown(1), # TODO Config cooldown times
                                          ChannelUserCommandCooldown(15) ])
        if self.chat.unregister_command(self.command_list['voices']):
            self.command_list['voices'] = self.config.get(section="BOT", option="voices_command")
            self.chat.register_command(self.command_list['voices'], 
                self._get_voices, command_middleware=[ChannelCommandCooldown(10), # TODO Config cooldown times
                                               ChannelUserCommandCooldown(15) ])
        if self.chat.unregister_command(self.command_list['voice']):
            self.command_list['voice'] = self.config.get(section="BOT", option="voice_command")
            self.chat.register_command(self.command_list['voice'], 
                self._set_voice, command_middleware=[ChannelUserCommandCooldown(10)])
        # self.end_session()


    def stop(self):
        if self.chat:
            self.chat.stop()


    async def _on_ready(self, ready_event: EventData):
        # Cannot put async or sync event triggers in this, as they are in different threads
        logger.info("Bot is ready")
        self.send_message(text="Chat DnD is now active! ⚔️🐉")
        await ready_event.chat.join_room(self.twitch_utils.channel.display_name) # or .login?

    
    def send_message(self, text: str):
        logger.debug(f"Sending chat msg: {text}")
        asyncio.run_coroutine_threadsafe(self.chat.send_message(text=text, room=self.twitch_utils.channel.display_name),
                                         asyncio.get_event_loop())


    def open_session(self):
        if not self.chat:
            return
        if self.session_mgr:
            self.session_mgr.end()
        self.session_mgr.open()
        self.chat.unregister_command(self.command_list['say'])
        self.chat.register_command(self.command_list['join'], self._add_user_to_queue, command_middleware=[ChannelUserCommandCooldown(30)])
        self.send_message(f"Session started! Type {self.chat._prefix}{self.command_list['join']} to queue for the adventuring party")
        chat_on_session_open.trigger()


    def start_session(self, party_size) -> bool:
        if self.session_mgr.start_session(party_size=party_size): # config 
            self.chat.unregister_command(self.command_list['join'])
            party = [x.name for x in self.session_mgr.session.party]
            self.chat.register_command(self.command_list['say'], self._say, command_middleware=[UserRestriction(allowed_users=[x.name for x in self.session_mgr.session.party]),
                                                                        ChannelCommandCooldown(10),
                                                                        ChannelUserCommandCooldown(15) ]) # TODO config cooldown times
            # TODO Send link to commands list (from git)
            self.send_message(f"Say welcome to our party members: {", ".join(party)}")
            self.send_message(f"Party members, type {self.chat._prefix}{self.command_list['say']} <msg> to have it spoken via TTS") 
            chat_on_session_start.trigger()
            return True
        else:
            self.send_message(f"Not enough party members in the queue! Type {self.chat._prefix}{self.command_list['join']}  to join ({len(self.session_mgr.session.queue)}/{party_size})")
            return False


    def end_session(self):
        if self.session_mgr:
            self.session_mgr.end()
        self.chat.unregister_command(self.command_list['say'])
        self.chat.unregister_command(self.command_list['join'])
        chat_on_session_end.trigger()


    async def _add_user_to_queue(self, cmd: ChatCommand):
        user: TwitchUser = await self.twitch_utils.get_user_by_name(username=cmd.user.name)
        if not user:
            return
        # TODO idea, provide other stats like vip/mod/status/badges? Can always fetch from twitchAPI especially since we cache for a week, aka no risk 
        # TODO we also want a default pfp perhaps if non exists
        member = await create_or_get_member(name=cmd.user.display_name, pfp_url = user.profile_image_url)
        if member not in self.session_mgr.session.queue:
            await cmd.reply(f'{member.name} added to queue')
            chat_on_join_queue.trigger([cmd.user.name])
        else:
            await cmd.reply(f'{member.name} already in the queue')
        self.session_mgr.join_queue(member)

    
    async def _say(self, cmd: ChatCommand):
        await asyncio.sleep(0.1)
        if cmd.parameter:
            # Event trigger *does* work here
            member = await fetch_member(cmd.user.name.lower())
            chat_say_command.trigger([member, cmd.parameter])


    async def _get_voices(self, cmd: ChatCommand):
        param = cmd.parameter
        if not param or param.upper().strip() not in [SOURCE_LOCAL.upper(), "11L", SOURCE_11L.upper()]:
            await cmd.reply(f"@{cmd.user.display_name} available TTS types are 'local', '11L'. Try {self.chat._prefix}{self.command_list['voices']} <type>")
            return
        param = param.upper().strip()
        msg = ""
        if param == SOURCE_LOCAL.upper():
            tts = LocalTTS(self.config, False)
            msg = tts.voice_list_message()
        elif param in [SOURCE_11L.upper(), '11L']:
            msg = ElevenLabsTTS.voices_messages()
        if not msg:
            return
        await cmd.reply(msg)


    async def _set_voice(self, cmd: ChatCommand):
        param = cmd.parameter
        if not param or not param.strip():
            await cmd.reply(f"@{cmd.user.display_name} Please specify a voice to set to. Find voices using {self.chat._prefix}{self.command_list['voices']} <type>")
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
               member = await create_or_get_member(name=cmd.user.display_name, pfp_url = user.profile_image_url)
               await update_tts(member, voice_id)
               msg = f"@{cmd.user.display_name} Successfully set TTS voice!"
            else:
                msg = f"@{cmd.user.display_name} Error setting TTS voice!"
        else:
            msg = f"@{cmd.user.display_name} Could not set TTS voice. Voice not available or not found."
        await cmd.reply(msg)

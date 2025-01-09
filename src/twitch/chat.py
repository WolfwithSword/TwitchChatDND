import asyncio
from twitchAPI.chat import Chat, ChatCommand, EventData
from twitchAPI.chat.middleware import UserRestriction, ChannelRestriction, ChannelCommandCooldown, ChannelUserCommandCooldown
from twitchAPI.object.api import TwitchUser
from twitchAPI.type import ChatEvent

from twitch.utils import TwitchUtils

from data import Member
from data.member import create_or_get_member, fetch_member
from chatdnd import SessionManager

from custom_logger.logger import logger

from helpers import TCDNDConfig as Config
from helpers import Event

from chatdnd.events.ui_events import ui_settings_bot_settings_update_event, ui_settings_twitch_channel_update_event
from chatdnd.events.chat_events import *
from chatdnd.events.twitchutils_events import twitchutils_twitch_on_connect_event

class ChatController(Chat):
    def __init__(self, session_mgr: SessionManager, config: Config):
        self.twitch_utils:TwitchUtils = None
        self.twitch: Twitch = None
        self.config: Config = config
        self.chat: Chat = None
        self.channel: TwitchUser = None

        self.session_mgr = session_mgr
        self.command_list = {}

        ui_settings_twitch_channel_update_event.addListener(self.start)
        twitchutils_twitch_on_connect_event.addListener(self.start)


    async def start(self, status: bool=None, twitch_utils: TwitchUtils=None, wait_tries:int = 5):
        self.channel = None
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

        self.channel = await self.twitch_utils.get_user_by_name(username=self.config.get(section="TWITCH", option="channel", fallback=''))
        if not self.channel:
            logger.error(f"Channel {self.config.get(section="TWITCH", option="channel", fallback=None)} not found")
            chat_on_channel_fetch.trigger([False])
            raise Exception("Channel not found")
        chat_on_channel_fetch.trigger([True])
        chat_bot_on_connect.trigger([False])
        self.chat = await Chat(self.twitch)#, initial_channel=self.channel.username)
        self.chat.register_event(ChatEvent.READY, self._on_ready)

        self.chat.set_prefix(self.config.get(section="BOT", option="prefix", fallback="!"))

        self.command_list['join'] = self.config.get(section="BOT", option="join_command")
        self.command_list['say'] = self.config.get(section="BOT", option="speak_command")

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
                                          ChannelCommandCooldown(10), # TODO Config cooldown times
                                          ChannelUserCommandCooldown(15) ])


    def stop(self):
        if self.chat:
            self.chat.stop()


    async def _on_ready(self, ready_event: EventData):
        # Cannot put async or sync event triggers in this, as they are in different threads
        logger.info("Bot is ready")
        self.send_message(text="Chat DnD is now active! ⚔️🐉")
        await ready_event.chat.join_room(self.channel.display_name)
        
        #### TODO remove, this is for testing without needing to start a whole session setup and activate.
        self.chat.register_command('saytest', self._say, command_middleware=[
                                                                    ChannelCommandCooldown(10),
                                                                    ChannelUserCommandCooldown(15) ]) # TODO config cooldown times
    
    
    def send_message(self, text: str):
        logger.debug(f"Sending chat msg: {text}")
        asyncio.run_coroutine_threadsafe(self.chat.send_message(text=text, room=self.channel.display_name),
                                         asyncio.get_event_loop())


    def open_session(self):
        if not self.chat:
            return
        if self.session_mgr:
            self.session_mgr.end()
        self.chat.unregister_command(self.command_list['say'])
        self.chat.register_command(self.command_list['join'], self._add_user_to_queue, command_middleware=[ChannelUserCommandCooldown(30)])
        self.send_message(f"Session started! Type {self.chat._prefix}{self.command_list['join']} to queue for the adventuring party")
        chat_on_session_open.trigger()


    def start_session(self):
        party_size = 4
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
        else:
            self.send_message(f"Not enough party members in the queue! Type {self.chat._prefix}{self.command_list['join']}  to join ({len(self.session_mgr.session.queue)}/{party_size})")

    def end_session(self):
        if self.session_mgr:
            self.session_mgr.end()
        self.chat.unregister_command('say')
        chat_on_session_end.trigger()


    async def _add_user_to_queue(self, cmd: ChatCommand):
        # TODO move to diff place? maybe not
        user: TwitchUser = await self.twitch_utils.get_user_by_name(username=cmd.user.name)
        if not user:
            return
        # TODO idea, provide other stats like vip/mod/status/badges? Can always fetch from twitchAPI especially since we cache for a week, aka no risk
        # TODO we also want a default pfp perhaps if non exists
        member = await create_or_get_member(name=cmd.user.display_name, pfp_url = user.profile_image_url)
        if member not in self.session_mgr.session.queue:
            await cmd.reply(f'{member.name} added to queue')
        else:
            await cmd.reply(f'{member.name} already in the queue')
        self.session_mgr.join_queue(member)

    
    async def _say(self, cmd: ChatCommand):
        await asyncio.sleep(0.1)
        if cmd.parameter:
            # Event trigger *does* work here
            member = await fetch_member(cmd.user.name.lower())
            chat_say_command.trigger([member, cmd.parameter])

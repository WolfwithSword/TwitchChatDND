import asyncio
from asyncio import Queue

from functools import wraps
from quart import Quart, websocket, send_from_directory

from data import Member
from data.voices import fetch_voice
from tts import LocalTTS, ElevenLabsTTS
from helpers import TCDNDConfig as Config
from helpers.utils import get_resource_path
from helpers.constants import SOURCE_11L, SOURCE_LOCAL
from custom_logger.logger import logger

from chatdnd.events.chat_events import chat_say_command
from chatdnd.events.session_events import on_party_update
from chatdnd.events.web_events import on_overlay_open


STATIC_DIR = get_resource_path("../server/static", from_resources=True)
message_queue = Queue()
members_queue = Queue()
clients = set()
overlay_clients = set()


def collect_tts_websockets(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        clients.add(websocket._get_current_object())
        try:
            return await func(*args, **kwargs)
        finally:
            clients.discard(websocket._get_current_object())

    return wrapper


def collect_member_websockets(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        overlay_clients.add(websocket._get_current_object())
        try:
            return await func(*args, **kwargs)
        finally:
            overlay_clients.discard(websocket._get_current_object())

    return wrapper


async def broadcast_tts(chunk):
    for websock in clients:
        await asyncio.wait_for(websock.send(chunk), timeout=10)


async def broadcast_member_update(message):
    for websock in overlay_clients:
        await asyncio.wait_for(websock.send_json(message), timeout=5)


class ServerApp:
    def __init__(self, config: Config):
        self.app = Quart(__name__)
        self.config = config
        self.tts = {
            SOURCE_LOCAL: LocalTTS(config),
            SOURCE_11L: ElevenLabsTTS(config, full_instance=True),
        }
        self._setup_routes()

        self._party: set[Member] = set()

        # Setup here temporarily for POC - or just keep tbh
        chat_say_command.addListener(self.chat_say)
        on_party_update.addListener(self.send_members)
        on_overlay_open.trigger()

    def _setup_routes(self):

        @self.app.websocket("/ws/tts")
        @collect_tts_websockets
        async def audio_stream():
            try:
                logger.debug("tts ws opened")
                await websocket.send_json({"type": "heartbeat"})
                while True:
                    if not message_queue.empty():
                        member, message = await message_queue.get()
                        speech_message = {
                            "type": "speech",
                            "name": member.name,
                            "message": message,
                        }
                        logger.info(f"saying '{message}' from {member}")
                        duration = 0
                        last_chunk_duration = 0
                        send_bounce = False

                        tts_type = SOURCE_LOCAL
                        voice_id = ""
                        if member and member.preferred_tts_uid:
                            _voice = await fetch_voice(uid=member.preferred_tts_uid)
                            if _voice:
                                voice_id = member.preferred_tts_uid
                                tts_type = _voice.source
                        async for chunk, _duration in self.tts[tts_type].get_stream(message, voice_id):
                            # TODO: Allow for break / interruption from emergency stuff - also hide stuff.
                            # Or yknow, just instruct to hide the browser source.
                            # Yeah, to mute, best to just hide the browser source.
                            if not send_bounce:
                                send_bounce = True
                                await self.animate_member(member.name, "bounce")
                                await members_queue.put(speech_message)
                            await broadcast_tts(chunk)
                            duration += _duration
                            last_chunk_duration = _duration
                        await asyncio.sleep(last_chunk_duration)
                        speech_message = {"type": "endspeech"}
                        await self.animate_member(member.name, "idle")
                        await asyncio.sleep(0.2)

                        await members_queue.put(speech_message)

                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(e)
            finally:
                logger.debug("tts ws closed")

        @self.app.websocket("/ws/members")
        @collect_member_websockets
        async def user_overlay_ws():
            try:
                await websocket.send_json({"type": "heartbeat"})
                logger.debug("overlay ws opened")
                await asyncio.sleep(0.3)
                on_overlay_open.trigger()
                await asyncio.sleep(0.3)
                while True:
                    while not members_queue.empty():
                        message = await members_queue.get()
                        logger.info(f"member msg {message}")
                        await broadcast_member_update(message)
                        await asyncio.sleep(0.05)
                    await asyncio.sleep(0.5)
            finally:
                logger.debug("overlay ws closed")

        @self.app.route("/overlay")
        async def overlay():
            return await send_from_directory(STATIC_DIR, "overlay.html")

    async def chat_say(self, member: Member, text: str):
        await message_queue.put((member, text))

    async def run_task(self, host="0.0.0.0", **kwargs):
        # TODO on port change, request app restart
        await self.app.run_task(
            host=host,
            port=self.config.getint(section="SERVER", option="port"),
            **kwargs,
        )

    async def send_members(self, members: list[Member] = None):
        if members is None:
            members = []
        user_data = [{"name": member.name, "pfp_url": member.pfp_url} for member in sorted(members)]
        if not user_data:
            speech_message = {"type": "endspeech"}
            await members_queue.put(speech_message)
        message = {"type": "update_users", "users": user_data}
        await members_queue.put(message)

    async def animate_member(self, name, anim_type):
        message = {"type": "animate", "name": name, "animation": anim_type}
        await members_queue.put(message)

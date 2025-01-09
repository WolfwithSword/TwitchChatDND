import asyncio
from asyncio import Queue

from quart import Quart, redirect, request, jsonify, websocket, render_template, send_from_directory, Response
import os, sys

from data import Member
from tts import LocalTTS
from helpers import TCDNDConfig as Config
from custom_logger.logger import logger

from chatdnd.events.chat_events import chat_say_command
from chatdnd.events.session_events import on_party_update
from chatdnd.events.web_events import on_overlay_open
from helpers.utils import get_resource_path


STATIC_DIR = get_resource_path("../server/static", from_resources=True)
message_queue = Queue()
members_queue = Queue()
clients = set()
overlay_clients = set()

class ServerApp():
    def __init__(self, config: Config):
        self.app = Quart(__name__)
        self.config = config
        self.tts = LocalTTS(config) # TODO both local and cloud
        self._setup_routes()

        self._party: set[Member] = set()

        # Setup here temporarily for POC
        chat_say_command.addListener(self.chat_say)
        on_party_update.addListener(self.send_members)
        on_overlay_open.trigger()

    def _setup_routes(self):
    
        @self.app.websocket("/ws/tts")
        async def audio_stream():
            clients.add(websocket) 
            try:
                logger.debug("tts ws opened")
                await websocket.send_json({"type":"heartbeat"})
                while True:
                    if not message_queue.empty():
                        member, message = await message_queue.get()
                        speech_message = {
                            "type": "speech",
                            "name": member.name,
                            "message": message
                        }
                        logger.info(f"saying '{message}' from {member}")
                        duration = 0
                        last_chunk_duration = 0
                        send_bounce = False
                        async for chunk, _duration in self.tts.get_stream(message, '' if not member else member.preferred_tts):
                            # TODO: Allow for break / interruption from emergency stuff - also hide stuff. Or yknow, just instruct to hide the browser source.
                            if not send_bounce:
                                send_bounce = True
                                await self.animate_member(member.name, "bounce")
                                await members_queue.put(speech_message)
                            await asyncio.wait_for(websocket.send(chunk), timeout=10)
                            duration += _duration
                            last_chunk_duration = _duration
                        await asyncio.sleep(last_chunk_duration)
                        speech_message = {
                            "type": "endspeech"
                        }
                        await self.animate_member(member.name, "idle")
                        await asyncio.sleep(0.3)
                        await members_queue.put(speech_message)

                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(e)
                pass
            finally:
                logger.debug("tts ws closed")
                clients.discard(websocket)

        @self.app.websocket("/ws/members")
        async def user_overlay_ws():
            overlay_clients.add(websocket)
            try:
                await websocket.send_json({"type":"heartbeat"})
                logger.debug('overlay ws opened')
                on_overlay_open.trigger()
                await asyncio.sleep(0.5)
                while True:
                    while not members_queue.empty():
                        message = await members_queue.get()
                        logger.info(f"member msg {message}")
                        await asyncio.wait_for(websocket.send_json(message), timeout=5)
                    await asyncio.sleep(0.5)
            finally:
                logger.debug('overlay ws closed')
                overlay_clients.discard(websocket)

        @self.app.route('/overlay')
        async def overlay():
            return await send_from_directory(STATIC_DIR, 'overlay.html')
    
    async def chat_say(self, member: Member, text: str):
        # If client was connected but dc'd, this can revive connection when it runs. But also, we don't want things to queue up forever... Might not be a problem, needs hard testing later
        # But cannot simply do an if check here for clients
        await message_queue.put((member, text))

            
    async def run_task(self, host="0.0.0.0", **kwargs):
        # TODO on port change, request app restart
        await self.app.run_task(host=host, port=self.config.getint(section="SERVER", option="port"), **kwargs)

    async def send_members(self, members: list[Member] = []):
        user_data = [{"name": member.name, "pfp_url": member.pfp_url} for member in sorted(members)]
        if not user_data:
            speech_message = {
                "type": "endspeech"
            }         
            await members_queue.put(speech_message)   
        message = {"type": "update_users", "users": user_data}
        await members_queue.put(message)
    
    async def animate_member(self, name, anim_type):
        message = {
            "type": "animate",
            "name": name,
            "animation": anim_type
        }
        await members_queue.put(message)

import asyncio
from asyncio import Queue

from quart import Quart, redirect, request, jsonify, websocket, render_template, send_from_directory, Response
import os, sys

from data import Member
from tts import LocalTTS
from helpers import TCDNDConfig as Config
from custom_logger.logger import logger

from chatdnd.events.chat_events import chat_say_command
from helpers.utils import get_resource_path


STATIC_DIR = get_resource_path("../server/static", from_resources=True)
message_queue = Queue()
clients = set()

class ServerApp():
    def __init__(self, config: Config):
        self.app = Quart(__name__)
        self.config = config
        self.tts = LocalTTS(config) # TODO both local and cloud
        self._setup_routes()

        # Setup here temporarily for POC
        chat_say_command.addListener(self.chat_say)


    def _setup_routes(self):
        @self.app.route('/test') # Temp / Testing
        async def test():
            logger.info("TEST QUART")
            return jsonify({"test": "123"})
    
        @self.app.websocket("/tts")
        async def audio_stream():
            clients.add(websocket) 
            try:
                logger.debug("ws opened")
                while True:
                    if not message_queue.empty():
                        member, message = await message_queue.get()
                        logger.info(f"saying {message} from {member}")

                        async for chunk in self.tts.get_stream(message, '' if not member else member.preferred_tts):
                            await asyncio.wait_for(websocket.send(chunk), timeout=10)
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(e)
                pass
            finally:
                logger.debug("ws closed")
                clients.discard(websocket)

        # This POST is *purely* for testing. We want actual triggers to be event driven to put text into the queue.
        # Final version, this will not be enabled. We will rely on event processing
        @self.app.route('/trigger-tts', methods=['POST']) # doesnt have to be a post
        async def trigger_tts():

            text = (await request.get_json()).get('text', 'Default message')  # Read text from POST body

            if not text:
                return jsonify({"error": "Text is required"}), 400
            
            if clients:
                await message_queue.put((None, text))
                return jsonify({"status": "success", "message": "Text sent to WebSocket for TTS."})
            else:
                return jsonify({"error": "No active WebSocket connection."}), 400

        @self.app.route('/overlay')
        async def overlay():
            return await send_from_directory(STATIC_DIR, 'overlay.html')
    
    async def chat_say(self, member: Member, text: str):
        logger.info(f"TTS saying '{text}' from {'UNKNOWN' if not member else member.name}")
        # If client was connected but dc'd, this can revive connection when it runs. But also, we don't want things to queue up forever... Might not be a problem, needs hard testing later
        # But cannot simply do an if check here for clients
        await message_queue.put((member, text))

            
    async def run_task(self, host="0.0.0.0", **kwargs):
        # TODO on port change, request app restart
        await self.app.run_task(host=host, port=self.config.getint(section="SERVER", option="port"), **kwargs)

import os, sys

import asyncio
import threading
import time
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Run the application.")
    parser.add_argument('--debug', action='store_true', help="Enable debug logging level.")
    return parser.parse_args()

args = parse_args()
os.environ['TCDND_DEBUG_MODE'] = '1' if args.debug else '0'

from twitch.utils import TwitchUtils
from twitch.chat import ChatController
from twitchAPI.type import TwitchAuthorizationException

from helpers import TCDNDConfig as Config
from ui.app import DesktopApp
from server.app import ServerApp

from _version import __version__

from chatdnd import SessionManager
from chatdnd.events.ui_events import ui_settings_twitch_auth_update_event, ui_settings_twitch_channel_update_event

from custom_logger.logger import logger
from db import initialize_database

cwd = os.getcwd()
config_path = os.path.join(cwd, 'config.ini')
cache_dir = os.path.join(cwd, '.tcdnd-cache/')

config = Config()
config.setup(config_path)

twitch_utils = TwitchUtils(config, cache_dir)

session_mgr: SessionManager = SessionManager()
chat: ChatController = ChatController(session_mgr, config)

server = ServerApp(config)

APP_RUNNING = True

async def run_twitch():

    async def try_setup():
        while not config.twitch_auth:
            await asyncio.sleep(5)
        logger.info("Starting Twitch Client...")

        try: 
            if twitch_utils.twitch:
                return True
            ui_settings_twitch_auth_update_event.trigger()
            await asyncio.sleep(5)
            if twitch_utils.twitch:
                return True
        except Exception as e:
            logger.error(f"Invalid Twitch Connection")
            logger.error(e)
        return False

    success = False
    while not success:
        success = await try_setup()
        await asyncio.sleep(1)
    try:
        while APP_RUNNING:
            await asyncio.sleep(0.5)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        await twitch_utils.twitch.close()


async def run_twitch_bot():
    while not twitch_utils.twitch:
        await asyncio.sleep(5)
    
    async def try_channel():
        while not config.get(section="TWITCH", option="channel", fallback=None):
            await asyncio.sleep(5)
        try:   
            if chat.channel:
                return True
            # await chat.start(twitch_utils)
            
            # ui_settings_twitch_channel_update_event.trigger([twitch_utils])
            await asyncio.sleep(4)
            if chat.channel:
                return True
            return False
        except Exception as e:
            if "Channel not found" in str(e):
                config.set(section="TWITCH", option="channel", value='')
                config.write_updates()
                return False
            raise
    
    success = False
    while not success:
        success = await try_channel()
        await asyncio.sleep(1)
    try:
        while APP_RUNNING:
            await asyncio.sleep(0.5)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        chat.stop()


logger.info("Starting")


async def run_server():
    await server.run_task(host="0.0.0.0")


async def run_ui():
    app = DesktopApp(session_mgr, chat, config, twitch_utils)
    while app.running:
        await asyncio.sleep(0.05)
        app.update()
    APP_RUNNING = False
    await asyncio.sleep(2)
    sys.exit(0)
    # app.mainloop()

async def run_all():
    tasks = [
        asyncio.create_task(initialize_database()),
        asyncio.create_task(run_server(), name="Server"),
        asyncio.create_task(run_twitch(), name="Twitch"),
        asyncio.create_task(run_ui(), name="UI"),
        asyncio.create_task(run_twitch_bot(), name="Twitch-Bot")
    ]

    try: 
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"An exception has occurred: {e}")
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.warning(f"{task.get_name()} task was cancelled")


if __name__ == "__main__":
    asyncio.run(run_all())
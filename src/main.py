import os
import sys

import asyncio
from queue import Queue
from logging import getLogger

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

from initialize import _args as args # Also runs some initializing logic on import

from helpers.instance_manager import init_cache, init_config
from helpers.constants import TTS_SOURCE
from tts import get_tts

from twitch.utils import TwitchUtils
from twitch.chat import ChatController

import helpers.event as _event_module
from helpers.utils import check_for_updates
from ui.app import DesktopApp
from server.app import ServerApp

from chatdnd import SessionManager
from chatdnd.events.ui_events import (
    ui_settings_twitch_auth_update_event,
    ui_on_startup_complete,
    ui_fetch_update_check_event,
)

from db import initialize_database

assert args is not None
logger = getLogger("ChatDND")
cwd = os.getcwd()

_tasks = Queue()

setattr(sys.modules[_event_module.__name__], "_TASK_QUEUE", _tasks)

if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS
    src_path = os.path.join(base_path, "src")
    sys.path.insert(0, src_path)


config_path = os.path.join(cwd, "config.ini")
cache_dir = os.path.join(cwd, ".tcdnd-cache/")

# Initialize config and cache
config = init_config(name='default', path=config_path)

if config.has_section('CACHE') and config.has_option(section="CACHE", option="directory"):
    cache_dir = config.get(section='CACHE', option='directory')
cache = init_cache(name='default', path=cache_dir)

if not config.has_option(section="CACHE", option="directory"):
    config.set(section="CACHE", option="directory", value=cache_dir)

def run_migrations():
    logger.info("Running DB Migrations...")
    if getattr(sys, "frozen", False):
        alembic_cfg = AlembicConfig(os.path.join(cwd, "alembic.ini"))
        script_location = os.path.join(cwd, "migrations")
    else:
        alembic_cfg = AlembicConfig(os.path.join(cwd, "alembic.ini"))
        script_location = os.path.join(os.path.dirname(__file__), "..", "migrations")
    logger.info(f"DB Migrations config: {alembic_cfg.config_file_name}")
    logger.info(f"DB Migrations folder: {script_location}")
    alembic_cfg.set_main_option("script_location", script_location)

    alembic_command.upgrade(alembic_cfg, "head")
    logger.info("Finished DB Migrations")


async def run_db_init():
    run_migrations()
    await initialize_database()


asyncio.run(run_db_init())  # "DB-Setup"

# Initialize TTS Engines
for source in TTS_SOURCE:
    get_tts(source)

twitch_utils = TwitchUtils()

session_mgr: SessionManager = SessionManager()
chat: ChatController = ChatController(session_mgr)

server = ServerApp()

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
        while not twitch_utils.channel:
            await asyncio.sleep(5)
        try:
            if twitch_utils.channel and chat.chat is not None and chat.chat.is_connected:
                return True
            await asyncio.sleep(4)
            if twitch_utils.channel and chat.chat is not None and chat.chat.is_connected:
                return True
            return False
        except Exception as e:
            if "Channel not found" in str(e):
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
    await server.run_task(host="0.0.0.0", port=config.getint(section="SERVER", option="port", fallback=5000))


async def run_ui():
    global APP_RUNNING
    app = DesktopApp(session_mgr, chat, twitch_utils)
    while app.running:
        await asyncio.sleep(1000/30/1000)
        app.update()
    APP_RUNNING = False
    await asyncio.sleep(2)
    sys.exit(0)


async def run_queued_tasks():
    while APP_RUNNING:
        try:
            callback = None
            _args = None
            if _tasks.empty():
                await asyncio.sleep(0.5)
            else:
                items = _tasks.get(False)
                callback = items[0]
                if len(items) > 1:
                    _args = items[1:]
                    callback(*_args)
                else:
                    callback()
        except Exception as e:
            logger.error(f"Error in queued task: {callback} ({_args}) - {e}")


async def startup_completion():
    await asyncio.sleep(6)
    ui_on_startup_complete.trigger()
    ui_fetch_update_check_event.trigger([check_for_updates()])


async def run_all():

    tasks = [
        asyncio.create_task(run_server(), name="Server"),
        asyncio.create_task(run_twitch(), name="Twitch"),
        asyncio.create_task(run_ui(), name="UI"),
        asyncio.create_task(run_twitch_bot(), name="Twitch-Bot"),
        asyncio.create_task(run_queued_tasks(), name="Task-Queue"),
        asyncio.create_task(startup_completion(), name="Finish-Startup"),
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

import os, sys
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine, TypeVar
import requests
from packaging.version import Version
from _version import __version__ as current_version

T = TypeVar("T")

def get_resource_path(relative_path, from_resources: bool = False):
    # Get absolute path to a resource, frozen or local (relative to helpers/utils.py)
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        if from_resources:
            relative_path = relative_path.replace("../", "")
            base_path = os.path.join(os.path.abspath("."), "resources")
        else:
            if not os.path.isfile(os.path.join(base_path, relative_path)):
                if not os.path.isdir(os.path.join(base_path, relative_path)):
                    base_path = os.path.dirname(os.path.abspath(__file__))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def run_coroutine_sync(coroutine: Coroutine[Any, Any, T], timeout: float = 30) -> T:
    def run_in_new_loop():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coroutine)
        finally:
            new_loop.close()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    if threading.current_thread() is threading.main_thread():
        if not loop.is_running():
            return loop.run_until_complete(coroutine)
        else:
            with ThreadPoolExecutor() as pool:
                future = pool.submit(run_in_new_loop)
                return future.result(timeout=timeout)
    else:
        return asyncio.run_coroutine_threadsafe(coroutine, loop).result()


def check_for_updates():
    owner = "WolfwithSword" # TODO consider moving to a metadata file?
    repo = "TwitchChatDND"
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    response = requests.get(url)
    if response.status_code != 200:
        return None

    data = response.json()
    if not data:
        return None
    latest_release = sorted(data, key = lambda d: d['published_at'], reverse=True)[0]
    latest = latest_release['tag_name']

    if current_version == 'dev':
        return f"https://github.com/{owner}/{repo}/releases/tag/{latest}"
    elif 'nightly' in current_version:
        return f"https://github.com/{owner}/{repo}/releases/tag/nightly"
    else:
        if Version(current_version.replace("v","")) < Version(latest.replace("v","")):
            return f"https://github.com/{owner}/{repo}/releases/tag/{latest}"
    return None
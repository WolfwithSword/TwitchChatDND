import os
from pathlib import Path
import atexit
from functools import lru_cache
from logging import getLogger
from diskcache import Cache

from helpers.config import TCDNDConfig as Config

# Eventually, this system will let us split up caches and configs
# but for now, will allow us to share a single instance much better
# and be able to get globally

logger = getLogger("ChatDND")

_cleanup_cbs = []

def register_cleanup(obj, method='close'):
    func = getattr(obj, method, None)
    if func and callable(func):
        _cleanup_cbs.append(func)

@atexit.register
def _cleanup():
    for func in _cleanup_cbs:
        try:
            func()
        except Exception as e:
            logger.warning(f"Could not close instance at exit: {func} - {e}")

#### Cache #####

_cache_registry = {}
_cache_store = {}

@lru_cache(maxsize=None)
def get_cache(name='default') -> Cache:
    cache = None
    if name in _cache_store:
        cache = _cache_store.get(name)
        return cache
    path = _cache_registry.get(name)
    if path:
        cache = Cache(directory=path)
    else:
        cache = Cache()
    _cache_store[name] = cache
    register_cleanup(cache)
    return cache


def init_cache(name='default', path=None) -> Cache:
    if name in _cache_registry:
        return get_cache(name)
    if path is None:
        logger.error(f"Attempted to initialize cache [{name}] without invalid path: {path}.")
        return get_cache(name)
    Path(path).mkdir(parents=True, exist_ok=True)
    _cache_registry[name] = path
    return get_cache(name)

################

#### Config ####

_config_registry = {}
_config_store = {}

@lru_cache(maxsize=None)
def get_config(name='default') -> Config:
    if name in _config_store:
        return _config_store.get(name)
    config = Config()
    path = _config_registry.get(name)
    if path:
        config.setup(path)
    _config_store[name] = config
    return config

def init_config(name='default', path=None) -> Config:
    if name in _config_registry:
        return get_config(name)
    if path is None or not os.path.isfile(path):
        logger.error(f"Attempted to initialize config [{name}] without invalid path: {path}.")
        return get_config(name)

    _config_registry[name] = path
    config = get_config(name)
    config.setup(path)
    _config_store[name] = config
    return config

def reload_cache(name='default'):
    if name in _config_registry:
        config = get_config(name)
        config.setup(_config_registry.get(name))

###############

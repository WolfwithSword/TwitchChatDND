import asyncio
import inspect

from custom_logger.logger import logger

# Main sets this at startup. It's cursed, but it works.
_TASK_QUEUE = None

class Event:
    def __init__(self):
        self.__listeners = []
        self._main_loop = asyncio.get_event_loop()


    @property
    def on(self):
        def wrapper(func):
            self.addListener(func)
            return func
        return wrapper


    def addListener(self, func):
        if func in self.__listeners:
            return
        self.__listeners.append(func)


    def removeListener(self, func):
        if func not in self.__listeners:
            return
        self.__listeners.remove(func)


    def trigger(self, args = None):
        if args is None:
            args = []
        if type(args) not in [list, tuple, dict]:
            args = [args]
        for func in self.__listeners:
            try:
                if inspect.iscoroutinefunction(func):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self._run_async_func(func, *args))
                    except Exception:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(self._run_async_func(func, *args))
                else:
                    func(*args)
            except RuntimeError as e:
                if "main thread is not in main loop" in str(e):
                    _TASK_QUEUE.put((func, *args))
                    continue
                else:
                    raise e from e
            except Exception as e:
                raise e from e


    async def _run_async_func(self, func, *args):
        try:
            await func(*args)
        except Exception as e:
            logger.error(f"Async Event Listener error: {e}")

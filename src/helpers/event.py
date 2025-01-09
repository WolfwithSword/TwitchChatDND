import asyncio
import inspect
import threading

from custom_logger.logger import logger 
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
        if func in self.__listeners: return
        self.__listeners.append(func)
    

    def removeListener(self, func):
        if func not in self.__listeners: return
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
                    except:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(self._run_async_func(func, *args))
                else:
                    func(*args)
            except RuntimeError as e:
                if "main thread is not in main loop" in str(e):
                    logger.error(f"Error: {e}. This is likely to occur when a trigger is fired from a separate thread to the UI thread.")
                    continue
                else:
                    raise
            except Exception as e:
                raise


    async def _run_async_func(self, func, *args):
        try: 
            await func(*args)
        except Exception as e:
            print(f"Async Event Listener error: {e}")
import logging
import os
import sys
import asyncio
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
from queue import Queue

_format = "%(asctime)s [%(threadName)s] [%(name)s] [%(module)s] [%(levelname)s] - %(message)s"

class CustomStreamHandler(logging.StreamHandler):
    def __init__(self):
        super().__init__()
        formatter = logging.Formatter(_format)
        self.setFormatter(formatter)

class CustomFileHandler(RotatingFileHandler):
    def __init__(self, log_file):
        super().__init__(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        formatter = logging.Formatter(_format)
        self.setFormatter(formatter)

class RedirectSysLogger(object):
    def __init__(self, logger, level):
       self.logger = logger
       self.level = level
       self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            if line.strip() and len(line.strip()) > 1:
                self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass

class CustomLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        debug_mode = os.environ['TCDND_DEBUG_MODE'] == '1'
        self.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

        self.log_queue = Queue()

        is_frozen = getattr(sys, 'frozen', False)

        if is_frozen:
            # if getattr(sys, '_MEIPASS', False):
            #     base_path = sys._MEIPASS
            # else:
            base_path = os.path.dirname(sys.executable)
            log_folder = os.path.join(base_path, 'logs')
        else:
            log_folder = os.path.join(os.getcwd(), 'logs')

        os.makedirs(log_folder, exist_ok=True)
        log_file = os.path.join(log_folder, 'app.log')

        if is_frozen:
            file_handler = CustomFileHandler(log_file)
            handlers = [file_handler]
        else:
            stream_handler = CustomStreamHandler()
            handlers = [stream_handler]

        self.listener = QueueListener(self.log_queue, *handlers, respect_handler_level=True)
        self.listener.start()

        queue_handler = QueueHandler(self.log_queue)
        self.logger.addHandler(queue_handler)

        self.logger.propagate = False

    def shutdown(self):
        self.listener.stop()

logger = CustomLogger("ChatDND").logger
sys.stdout = RedirectSysLogger(logger, logging.INFO)
sys.stderr = RedirectSysLogger(logger, logging.ERROR)
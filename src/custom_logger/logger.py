import logging

class CustomHandler(logging.StreamHandler):

    def __init__(self):
        logging.StreamHandler.__init__(self)
        formatter = logging.Formatter('%(asctime)s [%(threadName)s] [%(name)s] [%(module)s] [%(levelname)s] - %(message)s')
        self.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # TODO: Env var
logger.addHandler(CustomHandler())


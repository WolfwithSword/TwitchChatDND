import random

from data import Session, Member, SessionState
from custom_logger.logger import logger 

class SessionManager():
    def __init__(self):
        self.session = Session()

    def join_queue(self, member: Member):
        self.session.queue.add(member)

    def start_session(self, party_size: int = 4) -> bool:
        if len(self.session.queue) < party_size:
            return False 
        self.session.state = SessionState.STARTED
        self.session.party.clear()
        self.session.queue.clear()
        self.session.party.update(random.sample(sorted(self.session.queue), party_size))
        return True
    
    def end(self):
        self.session.clear()
        self.session.state = SessionState.NONE

    def open(self):
        self.session.state = SessionState.OPEN

from data import Session, Member

from custom_logger.logger import logger 

class SessionManager():
    def __init__(self):
        self.session = Session()

    def join_queue(self, member: Member):
        self.session.queue.add(member)

    def start_session(self, party_size: int = 4) -> bool:
        if len(self.session.queue) < party_size:
            return False
        self.session.party.clear()
        self.session.party.update(random.sample(self.session.queue, party_size))
        return True
    
    def end(self):
        self.session.clear()
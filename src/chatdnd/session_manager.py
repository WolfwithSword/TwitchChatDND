import random

from data import Session, Member, SessionState
from chatdnd.events.session_events import on_party_update
from chatdnd.events.web_events import on_overlay_open


class SessionManager:
    def __init__(self):
        self.session = Session()
        on_overlay_open.addListener(self.trigger_update)
        on_party_update.trigger([self.session.get_party()])

    def join_queue(self, member: Member):
        self.session.queue.add(member)

    def start_session(self, party_size: int = 4) -> bool:
        if len(self.session.queue) < party_size:
            return False
        self.session.state = SessionState.STARTED
        self.session.party.clear()
        self.session.party.update(random.sample(sorted(self.session.queue), party_size))
        self.session.queue.clear()
        on_party_update.trigger([self.session.get_party()])
        return True

    def end(self):
        self.session.clear()
        self.session.state = SessionState.NONE
        on_party_update.trigger([self.session.get_party()])

    def open(self):
        self.session.clear()
        self.session.state = SessionState.OPEN
        on_party_update.trigger([self.session.get_party()])

    def trigger_update(self):
        on_party_update.trigger([self.session.get_party()])

from typing import Set, List
from enum import Enum, auto

from data.member import Member


class SessionState(Enum):
    NONE = auto()
    OPEN = auto()
    STARTED = auto()


class Session:

    def __init__(self):
        self.queue: Set[Member] = set()
        self.party: Set[Member] = set()
        self.state: SessionState = SessionState.NONE

    def join_queue(self, member: Member):
        self.queue.add(member)

    def clear(self):
        self.queue.clear()
        self.party.clear()
        self.state: SessionState = SessionState.NONE

    def get_party(self) -> List[Member]:
        return sorted(self.party)

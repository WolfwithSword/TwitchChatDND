from typing import Set, List
import random

from data.member import Member

class Session():

    def __init__(self):
        self.queue: Set[Member] = set()
        self.party: Set[Member] = set()

    def join_queue(self, member: Member):
        self.queue.add(member)

    def clear(self):
        self.queue.clear()
        self.party.clear()

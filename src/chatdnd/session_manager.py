import asyncio
import random

from data import Session, Member, SessionState
from data.member import members_end_session
from chatdnd.events.session_events import on_party_update, on_active_party_update, session_refresh_member
from chatdnd.events.web_events import on_overlay_open
from chatdnd.events.chat_events import chat_on_party_modify, chat_force_party_start_setup
from chatdnd.events.ui_events import ui_request_floating_notif, ui_force_home_party_update

from custom_logger.logger import logger
from ui.widgets.CTkFloatingNotifications.notification_type import NotifyType


class SessionManager:
    def __init__(self):
        self.session = Session()
        on_overlay_open.addListener(self.trigger_update)
        on_party_update.trigger([self.session.get_party()])
        chat_on_party_modify.addListener(self.update_party)
        session_refresh_member.addListener(self.refresh_member)

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

    def update_party(self, member: Member, remove: bool = False):
        if not remove and self.session.state != SessionState.STARTED:
            self.session.queue.clear()
            self.session.queue.add(member)
            self.start_session(1)
            chat_force_party_start_setup.trigger()
            ui_force_home_party_update.trigger()
            return

        _max = 8
        if len(self.session.party) >= _max and not remove:
            logger.warning(f"Max party size is {_max} due to screen space limitations. Cannot add a new member unless one is kicked")
            msg = f"Party is full ({len(self.session.party)}/{_max}). Remove someone first!"
            ui_request_floating_notif.trigger(
                [
                    msg,
                    NotifyType.WARNING,
                    {"duration": 8000},
                ]
            )
            return
        if not remove:
            self.add_member(member)
        else:
            self.remove_member(member)

    def add_member(self, member: Member):
        if member not in self.session.party:
            self.session.party.add(member)
            on_party_update.trigger([self.session.get_party()])
            on_active_party_update.trigger()

    def remove_member(self, member: Member, skip_db_update: bool = False):
        if member in self.session.party:
            self.session.party.remove(member)
            if not skip_db_update:
                on_party_update.trigger([self.session.get_party()])
                on_active_party_update.trigger()
                asyncio.create_task(members_end_session([member]))

    def refresh_member(self, member: Member):
        if member not in self.session.party:
            return
        self.remove_member(member, True)
        self.add_member(member)

    def end(self):
        asyncio.create_task(members_end_session(list(self.session.party)))
        self.session.clear()
        self.session.state = SessionState.NONE
        on_party_update.trigger([self.session.get_party()])

    def open(self):
        self.session.clear()
        self.session.state = SessionState.OPEN
        on_party_update.trigger([self.session.get_party()])

    def trigger_update(self):
        on_party_update.trigger([self.session.get_party()])

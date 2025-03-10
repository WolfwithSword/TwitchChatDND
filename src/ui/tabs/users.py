import asyncio
import customtkinter as ctk
from ui.widgets.member_card import MemberCard
from data.member import fetch_paginated_members

from twitch.chat import ChatController


class UsersTab:
    def __init__(self, parent, chat_ctrl: ChatController):
        self.parent = parent
        self.chat_ctrl = chat_ctrl

        self.load_members_lock = asyncio.Lock()

        self.page = 1
        self.per_page = 6 * 4
        self.name_filter = ""
        self.members_list_frame = ctk.CTkScrollableFrame(self.parent)
        self.members_list_frame.pack(padx=20, pady=20, fill="both", expand=True)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.update_search_filter)

        search_label = ctk.CTkLabel(self.parent, text="Search")
        search_label.pack(side=ctk.LEFT, padx=(8, 4), pady=10)
        self.search_box = ctk.CTkEntry(
            self.parent,
            textvariable=self.search_var,
            placeholder_text="Search by name...",
            width=260,
        )
        self.search_box.pack(side=ctk.LEFT, padx=(4, 10), pady=10)

        self.prev_button = ctk.CTkButton(self.parent, text="Previous", command=self.previous_page)
        self.prev_button.pack(side=ctk.LEFT, padx=10, pady=10)

        self.next_button = ctk.CTkButton(self.parent, text="Next", command=self.next_page)
        self.next_button.pack(side=ctk.LEFT, padx=10, pady=10)

        self.refresh_button = ctk.CTkButton(self.parent, text="Refresh", command=self.schedule_load_members)
        self.refresh_button.pack(side=ctk.RIGHT, padx=10, pady=10)

        self.load_members_task = asyncio.create_task(self.load_members())

    def update_search_filter(self, *args):
        self.name_filter = self.search_var.get()
        self.page = 1
        asyncio.create_task(self.delay_load_members())

    async def delay_load_members(self):
        await asyncio.sleep(0.2)
        self.schedule_load_members()

    def schedule_load_members(self):
        if self.load_members_task:
            self.load_members_task.cancel()
        self.load_members_task = asyncio.create_task(self.load_members())

    async def load_members(self):
        # Clear current members
        async with self.load_members_lock:
            for widget in self.members_list_frame.winfo_children():
                widget.destroy()

            try:
                await asyncio.sleep(0.2)
                members = await fetch_paginated_members(self.page, self.per_page, name_filter=self.name_filter)

                new_cards = list()
                columns = 6
                for member in members:
                    member_card = MemberCard(self.members_list_frame, member, self.chat_ctrl.config)
                    new_cards.append(member_card)
                new_cards = sorted(new_cards[:], key=lambda x: x.member.name)
                for index, card in enumerate(new_cards):
                    row = index // columns
                    col = index % columns
                    card.grid(row=row, column=col, padx=10, pady=10)

                self.update_pagination_buttons()
            except asyncio.CancelledError:
                pass

    def update_pagination_buttons(self):
        self.prev_button.configure(state="normal" if self.page > 1 else "disabled")
        self.next_button.configure(state=("normal" if len(self.members_list_frame.winfo_children()) == self.per_page else "disabled"))

    def previous_page(self):
        if self.page > 1:
            self.page -= 1
        self.schedule_load_members()

    def next_page(self):
        self.page += 1
        self.schedule_load_members()

import asyncio
import customtkinter as ctk
from CTkToolTip import CTkToolTip
from ui.widgets.CTkPopupMenu.custom_popupmenu import CTkContextMenu
from ui.widgets.member_card import MemberCard
from data.member import create_or_get_member, fetch_paginated_members
from chatdnd.events.ui_events import on_external_member_change
from twitch.chat import ChatController


class UsersTab:
    def __init__(self, parent, chat_ctrl: ChatController, context_menu: CTkContextMenu):
        self.parent = parent
        self.chat_ctrl = chat_ctrl
        self.context_menu = context_menu

        self.load_members_lock = asyncio.Lock()

        self.page = 1
        self.per_page = 6 * 3
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

        self.add_var = ctk.StringVar()

        self.add_btn = ctk.CTkButton(self.parent, text="Add", command=self.add_by_name, width=50)
        self.add_btn.pack(side=ctk.LEFT, padx=(20, 4), pady=10)
        self.add_box = ctk.CTkEntry(
            self.parent,
            textvariable=self.add_var,
            placeholder_text="Add by name...",
            width=220,
        )
        self.add_box.bind("<Return>", command=self.add_by_name)
        self.add_box.pack(side=ctk.LEFT, padx=(4, 10), pady=10)

        self.refresh_button = ctk.CTkButton(self.parent, text="Refresh", command=self.schedule_load_members)
        self.refresh_button.pack(side=ctk.RIGHT, padx=10, pady=10)

        self.load_members_task = asyncio.create_task(self.load_members())
        on_external_member_change.addListener(self.schedule_load_members)

        self.prev_tooltip = CTkToolTip(self.prev_button, message=f"{self.page if self.page == 1 else self.page - 1}", delay=0.3, corner_radius=50)
        self.next_tooltip = CTkToolTip(self.next_button, message=f"{self.page + 1}", delay=0.3, corner_radius=50)

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
                await asyncio.sleep(0.1)
                members = await fetch_paginated_members(self.page, self.per_page, name_filter=self.name_filter)

                new_cards = [
                    MemberCard(self.members_list_frame, member, self.context_menu, self.chat_ctrl) for member in members
                ]

                columns = 6
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
        self.prev_tooltip.configure(message=f"{self.page if self.page == 1 else self.page - 1}")
        self.next_tooltip.configure(message=f"{self.page + 1 if len(self.members_list_frame.winfo_children()) == self.per_page else self.page}")

    def previous_page(self):
        if self.page > 1:
            self.page -= 1
        self.schedule_load_members()

    def next_page(self):
        self.page += 1
        self.schedule_load_members()

    def add_by_name(self, event=None):
        async def _run():
            if not self.add_var.get():
                return
            user = await self.chat_ctrl.twitch_utils.get_user_by_name(username=self.add_var.get())
            if not user:
                return
            member = await create_or_get_member(name=user.display_name, pfp_url=user.profile_image_url)
            if member:
                self.schedule_load_members()

        asyncio.create_task(_run())

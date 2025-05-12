import customtkinter as ctk
from custom_logger.logger import logger

from ui.widgets.CTkPopupMenu.custom_popupmenu import CTkContextMenu, ContextMenuTypes
from ui.widgets.member_card import MemberCard
from twitch.chat import ChatController
from chatdnd.events.chat_events import (
    chat_on_join_queue,
    chat_bot_on_connect,
    chat_say_command,
)

from chatdnd.events.session_events import on_active_party_update
from chatdnd.events.ui_events import ui_force_home_party_update


class HomeTab:
    def __init__(self, parent, chat_ctrl: ChatController, context_menu: CTkContextMenu):
        self.parent = parent
        self.config = chat_ctrl.config
        self.chat_ctrl = chat_ctrl
        self.context_menu = context_menu

        self.parent.grid_columnconfigure(1, weight=0)
        self.parent.grid_columnconfigure((0, 2), weight=1)
        self.parent.grid_rowconfigure((0, 1), weight=0)
        self.parent.grid_rowconfigure((2, 3), weight=1)

        label = ctk.CTkLabel(self.parent, text="Session Management")
        label.place(anchor=ctk.CENTER, relx=0.5, rely=0.02)

        ####### Configure Session #######
        _inner_frame = ctk.CTkFrame(self.parent)
        _inner_frame.grid(row=1, column=0, sticky="nw", pady=(40, 4))

        self.open_button = ctk.CTkButton(_inner_frame, text="Open New Session", command=self._open_session)
        self.open_button.grid(row=0, column=0, sticky="nw", padx=(4, 4), pady=2)
        self.open_button.configure(state="disabled")

        self.session_status_var = ctk.StringVar(value="None")  # None, Open, Started
        session_status_label = ctk.CTkLabel(_inner_frame, textvariable=self.session_status_var, height=20, width=150)
        session_status_label.grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.party_size_var = ctk.IntVar(value=self.config.getint(section="DND", option="party_size", fallback=4))
        self.party_label_var = ctk.StringVar(value=f"Party Size - {self.party_size_var.get()}")
        party_label = ctk.CTkLabel(_inner_frame, textvariable=self.party_label_var)
        party_label.grid(row=1, column=0, pady=(16, 4), columnspan=2)

        self.party_size_slider = ctk.CTkSlider(
            _inner_frame,
            from_=1,
            to=6,
            number_of_steps=5,
            variable=self.party_size_var,
            command=self._update_party_limit,
            height=20,
        )
        self.party_size_slider.grid(row=2, column=0, columnspan=2, pady=(2, 30))

        self.start_session = ctk.CTkButton(_inner_frame, text="Start Session", command=self._start_session)
        self.start_session.grid(row=3, column=0, sticky="sw", padx=(4, 2), pady=2)
        self.start_session.configure(state="disabled")

        self.end_button = ctk.CTkButton(_inner_frame, text="End Session", command=self._end_session)
        self.end_button.grid(row=3, column=1, sticky="se", padx=(2, 4), pady=2)
        self.end_button.configure(state="disabled")

        ##################################

        ####### Session Queue #######

        _inner_frame_queue = ctk.CTkFrame(self.parent)
        _inner_frame_queue.grid(row=2, column=0, sticky="nw", pady=(6, 4))
        self.queue_label_var = ctk.StringVar(value=f"{len(self.chat_ctrl.session_mgr.session.queue)} in Queue")
        queue_label = ctk.CTkLabel(_inner_frame_queue, textvariable=self.queue_label_var, height=20, width=306)
        queue_label.pack(pady=(8, 4))

        self.queue_list = ctk.CTkScrollableFrame(_inner_frame_queue, height=360)
        self.queue_list.pack(padx=4, pady=4, fill="both", expand=True)

        chat_on_join_queue.addListener(self.add_queue_user)
        chat_bot_on_connect.addListener(self._allow_session_management)

        ##################################

        ####### Party View #######

        self._party_frame = ctk.CTkFrame(self.parent, width=550, height=586)
        self._party_frame.place(relx=0.268, rely=0.057)
        self._party_frame.grid_propagate(False)
        self._fill_party_frame()

        ##################################

        ####### Chat View #######

        # TODO Listen to chat events, display <user>:<msg>. Append to scrollframe, make it move. Make visually distinct?
        self._chat_frame = ctk.CTkScrollableFrame(self.parent, width=288, height=574)
        self._chat_frame.place(relx=0.740, rely=0.057)
        chat_say_command.addListener(self._add_chat_msg)

        ##################################

        on_active_party_update.addListener(self._fill_party_frame)
        ui_force_home_party_update.addListener(self._on_session_start)

    def _add_chat_msg(self, member, message):
        name = member.name

        msg_frame = ctk.CTkFrame(self._chat_frame)
        msg_frame.pack(fill="x", pady=5, padx=2, anchor="w")

        username_label = ctk.CTkLabel(
            msg_frame,
            text=f"{name}:",
            font=("Arial", 12, "bold"),
            text_color="#e8e8e8",
            justify="left",
            anchor="nw",
        )
        username_label.grid(row=0, column=0, padx=(6, 3), pady=(2, 4), sticky="nw")

        available_width = self._chat_frame.winfo_width() - 30

        message_label = ctk.CTkLabel(
            msg_frame,
            text=message,
            font=("Arial", 12),
            wraplength=available_width,
            text_color="#c8c8c8",
            justify="left",
            anchor="w",
        )
        message_label.grid(row=1, column=0, padx=(6, 2), pady=(2, 8), sticky="w")

        self._chat_frame.after(100, lambda: self._chat_frame._parent_canvas.yview_moveto(1.0))

    def _clear_chat_log(self):
        for widget in self._chat_frame.winfo_children():
            widget.destroy()

    def _fill_party_frame(self):
        for child in self._party_frame.winfo_children():
            child.destroy()

        columns = 3
        for index, member in enumerate(sorted(self.chat_ctrl.session_mgr.session.party)):
            row = index // columns
            col = index % columns
            member_card = MemberCard(
                self._party_frame,
                member,
                self.context_menu,
                self.chat_ctrl,
                self.config,
                width=130,
                height=170,
                textsize=10,
            )
            member_card.grid(row=row, column=col, padx=(35, 10), pady=(12, 12), sticky="w")

    def _allow_session_management(self, status: bool):
        if status:
            self.open_button.configure(state="normal")
            self._end_session()
        else:
            self.open_button.configure(state="disabled")

    def _open_session(self):
        for child in self.queue_list.winfo_children():
            child.destroy()
        logger.debug("Button pressed to open session")
        self.chat_ctrl.open_session()
        self.queue_label_var.set(value=f"{len(self.chat_ctrl.session_mgr.session.queue)} in Queue")
        self.session_status_var.set(value=self.chat_ctrl.session_mgr.session.state.name.capitalize())
        self.party_size_slider.configure(state="normal")
        self.start_session.configure(state="normal")
        self.end_button.configure(state="disabled")
        self._fill_party_frame()
        self._clear_chat_log()

    def _start_session(self):
        result = self.chat_ctrl.start_session(self.party_size_var.get())
        if result:
            self._on_session_start()

    def _on_session_start(self):
        for child in self.queue_list.winfo_children():
            child.destroy()
        self.queue_label_var.set(value=f"{len(self.chat_ctrl.session_mgr.session.queue)} in Queue")
        self.session_status_var.set(value=self.chat_ctrl.session_mgr.session.state.name.capitalize())
        self.party_size_slider.configure(state="disabled")
        self.start_session.configure(state="disabled")
        self.end_button.configure(state="normal")
        self._fill_party_frame()
        self._clear_chat_log()

    def _end_session(self):
        self.chat_ctrl.end_session()
        for child in self.queue_list.winfo_children():
            child.destroy()
        self.queue_label_var.set(value=f"{len(self.chat_ctrl.session_mgr.session.queue)} in Queue")
        self.session_status_var.set(value=self.chat_ctrl.session_mgr.session.state.name.capitalize())
        self.party_size_slider.configure(state="normal")
        self.start_session.configure(state="disabled")
        self.end_button.configure(state="disabled")
        self._fill_party_frame()
        self._clear_chat_log()

    def add_queue_user(self, name):
        user_label = ctk.CTkLabel(self.queue_list, text=name, anchor="e")
        user_label.pack(padx=(2, 6), pady=4)
        self.queue_label_var.set(value=f"{len(self.chat_ctrl.session_mgr.session.queue)} in Queue")

        def show_queue_ctx_menu(event):
            try:
                if self.context_menu.type != ContextMenuTypes.QUEUE_ENTRY:
                    self.context_menu.clear_contents()
                    self.context_menu.add_command(label="Remove", command=lambda: self.remove_queue_user(name), padx=(4, 5))
                else:
                    children = self.context_menu.prep_for_rewrite()
                    children[0].configure(command=lambda: self.remove_queue_user(name))
                self.context_menu.type = ContextMenuTypes.QUEUE_ENTRY
                self.parent.after(50, self.context_menu.popup(event.x_root, event.y_root))
            finally:
                self.context_menu.grab_release()

        user_label.bind("<Button-3>", show_queue_ctx_menu)

    def remove_queue_user(self, name):
        in_queue = False
        for member in list(self.chat_ctrl.session_mgr.session.queue):
            if member.name == name:
                self.chat_ctrl.session_mgr.session.queue.remove(member)
                in_queue = True
                break

        if not in_queue:
            return

        for child in self.queue_list.winfo_children():
            if child.cget("text") == name:
                child.destroy()
                break

        self.queue_label_var.set(value=f"{len(self.chat_ctrl.session_mgr.session.queue)} in Queue")

    def _update_party_limit(self, value):
        if int(value) != self.config.getint(section="DND", option="party_size", fallback=-1):
            self.party_label_var.set(f"Party Size - {int(value)}")
            self.config.set(section="DND", option="party_size", value=str(int(value)))
            self.config.write_updates()

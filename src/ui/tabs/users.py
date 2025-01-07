import customtkinter as ctk
from custom_logger.logger import logger

from twitch.chat import ChatController

class UsersTab():
    def __init__(self, parent, chat_ctrl: ChatController):
        self.parent = parent
        self.chat_ctrl = chat_ctrl
        label = ctk.CTkLabel(self.parent, text="Welcome to Users")
        label.pack(pady=10)

        button = ctk.CTkButton(self.parent, text="Click Me!")
        button.pack(pady=10)

        # TODO depends on what we think we want here
        # For ex, do we want to search the *entire* member's database table for users, and can modify them at whim?
        # Or should this be purely for a party/session members configuration?
        # Or could we do both? idk, what is the usefulness of any
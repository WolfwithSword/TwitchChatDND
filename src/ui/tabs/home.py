import customtkinter as ctk
from custom_logger.logger import logger

from twitch.chat import ChatController

# TODO: Display current active party on session start as MemberCards (smaller than on users page)

class HomeTab():
    def __init__(self, parent, chat_ctrl: ChatController):
        self.parent = parent
        self.config = chat_ctrl.config
        self.chat_ctrl = chat_ctrl
        
        label = ctk.CTkLabel(self.parent, text="Welcome to Home")
        label.pack(pady=10)

        button = ctk.CTkButton(self.parent, text="Open New Session", command=self._open_session)
        button.pack(pady=10)
  
        party_size_var = ctk.IntVar(value=self.config.getint(section="DND", option="party_size", fallback=4))
        self.party_label_var = ctk.StringVar(value=f"Party Size - {party_size_var.get()}")
        party_label = ctk.CTkLabel(self.parent, textvariable=self.party_label_var)
        party_label.pack(padx=(10,10), pady=(4,2))

        party_size_slider = ctk.CTkSlider(self.parent, from_=1, to=6,number_of_steps=5, variable=party_size_var, command=self._update_party_limit, height=20)
        party_size_slider.pack(padx=(20,20), pady=(2, 100))  

        
        button2 = ctk.CTkButton(self.parent, text="Test TTS Stream", command=self._tts_test)
        button2.pack(pady=10)

    def _open_session(self):
        logger.debug("Button pressed to open session")
        self.chat_ctrl.open_session() 
        
    def _update_party_limit(self, value):
        if int(value) != self.config.getint(section="DND", option="party_size", fallback=-1):
            self.party_label_var.set(f"Party Size - {int(value)}")
            self.config.set(section="DND", option="party_size", value=str(int(value)))
            self.config.write_updates()

    def _tts_test(self):
        logger.info("Testing TTS at local webserver")
import customtkinter as ctk
from PIL import Image
import requests
from io import BytesIO
import asyncio

from data import Member
from custom_logger.logger import logger

from tts import LocalTTS
from data.member import update_tts

class MemberCard(ctk.CTkFrame):
    def __init__(self, parent, member: Member, width=160, height=200, *args, **kwargs):
        super().__init__(parent, width=width, height=height, *args, **kwargs)
        self.member: Member = member
        self.width = width
        self.height = height
        self.grid_propagate(False)
        self.create_card()

        self.bind("<Button-1>", self.open_edit_popup)
        self.configure(cursor="hand2")

    def create_card(self):
        self.setup_pfp()

        name_label = ctk.CTkLabel(self, text=self.member.name.upper(), font=("Arial", 12), wraplength=self.width-10)
        name_label.grid(row=2, column=0, sticky="s", padx=5, pady=(2,10))
        name_label.bind("<Button-1>", self.open_edit_popup)

    def setup_pfp(self):
        try:
            url = self.member.pfp_url
            response = requests.get(url)
            img_data = response.content
            img = Image.open(BytesIO(img_data))

            img = img.resize((self.width, self.height), Image.LANCZOS)

            self.bg_image = ctk.CTkImage(img, img, (self.width, self.width))

            self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
            self.bg_label.grid(row=0, column=0, sticky="nsew", rowspan=2)
            self.bg_label.bind("<Button-1>", self.open_edit_popup)
        except Exception as e:
            logger.warn(f"Could not fetch image for {self.member}. {e}")
            self.bg_image = None
            self.bg_label = ctk.CTkLabel(self, text="No Image", font=("Arial", 10))
            self.bg_label.grid(row=0, column=0, sticky="nsew")
            self.bg_label.bind("<Button-1>", self.open_edit_popup)

    def open_edit_popup(self, event=None):
        MemberEditCard(self.member)

class MemberEditCard(ctk.CTkToplevel):
    open_popup = None

    def __init__(self, member: Member):
        if MemberEditCard.open_popup is not None:
            MemberEditCard.open_popup.focus_set()
            return

        super().__init__()
        MemberEditCard.open_popup = self
        self.member: Member = member
        self.title(f"Edit {self.member.name.upper()}")
        self.geometry("400x400")
        self.resizable(False, False)
        self.localTTS = LocalTTS(None)

        self.attributes("-topmost", True)

        self.create_widgets()

        self.protocol("WM_DELETE_WINDOW", self.close_popup) 
        #self.deiconify() 


    def create_widgets(self):
        self.label = ctk.CTkLabel(self, text="Preferred TTS:")
        self.label.pack(pady=(20, 5))


        self.tts_options = list(self.localTTS.get_voices().keys())  # Get keys from the voices dict
        self.tts_dropdown = ctk.CTkOptionMenu(
            self, values=self.tts_options
        )
        self.tts_dropdown.set(self.member.preferred_tts or self.tts_options[0])
        self.tts_dropdown.pack(pady=(5, 20))

        
        self.test_button = ctk.CTkButton(self, text="Preview", command=self.test_tts)
        self.test_button.pack(pady=10)

        self.save_button = ctk.CTkButton(self, text="Save", command=self.save_changes)
        self.save_button.pack(pady=10)


    def test_tts(self):
        self.localTTS.test_speak(voice=self.tts_dropdown.get())

    def save_changes(self):
        new_tts = self.tts_dropdown.get()
        self.member.preferred_tts = new_tts

        asyncio.create_task(update_tts(self.member, new_tts))
        logger.info(f"Updated preferred_tts for {self.member.name} to {new_tts}")

    def close_popup(self):
        MemberEditCard.open_popup = None
        self.destroy()

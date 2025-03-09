
from io import BytesIO
import asyncio
import requests
import customtkinter as ctk
from PIL import Image

from data import Member
from custom_logger.logger import logger

from tts import LocalTTS, ElevenLabsTTS
from data.member import update_tts, fetch_member
from helpers import TCDNDConfig as Config
from helpers.utils import run_coroutine_sync
from helpers.constants import SOURCES, SOURCE_11L, SOURCE_LOCAL

class MemberCard(ctk.CTkFrame):
    def __init__(self, parent, member: Member, config: Config, width=160, height=200, textsize=12, *args, **kwargs):
        super().__init__(parent, width=width, height=height, *args, **kwargs)
        self.member: Member = member
        self.config: Config = config
        self.width = width
        self.height = height
        self.textsize = textsize
        self.grid_propagate(False)
        self.create_card()

        self.bind("<Button-1>", self.open_edit_popup)
        self.configure(cursor="hand2")

    def create_card(self):
        self.setup_pfp()

        name_label = ctk.CTkLabel(self, text=self.member.name.upper(), font=("Arial", self.textsize), wraplength=self.width-10)
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
            self.bg_label = ctk.CTkLabel(self, text="No Image", font=("Arial", self.textsize))
            self.bg_label.grid(row=0, column=0, sticky="nsew")
            self.bg_label.bind("<Button-1>", self.open_edit_popup)

    def open_edit_popup(self, event=None):
        self.member = run_coroutine_sync(fetch_member(name=self.member.name))
        MemberEditCard(self.member, self.config)

class MemberEditCard(ctk.CTkToplevel):
    open_popup = None

    def __init__(self, member: Member, config: Config):
        if MemberEditCard.open_popup is not None:
            MemberEditCard.open_popup.focus_set()
            return

        super().__init__()
        MemberEditCard.open_popup = self
        self.member: Member = member
        self.config: Config = config
        self.title(f"Edit {self.member.name.upper()}")
        self.geometry("400x400")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close_popup)

        self.tts = {
            SOURCE_LOCAL: LocalTTS(self.config, False),
            SOURCE_11L: ElevenLabsTTS(self.config)
        }

        self.attributes("-topmost", True)

        self.create_widgets()
        #self.deiconify()


    def create_widgets(self):
        # TODO add stuff, make pretty, idk
        label1 = ctk.CTkLabel(self, text="TTS Voice Source:")
        label1.pack(pady=(20, 5))


        self.label = ctk.CTkLabel(self, text="TTS Voice:")
        self.label.pack(pady=(20, 5))

        current_source = SOURCE_LOCAL

        db_member = run_coroutine_sync(fetch_member(name=self.member.name))
        if db_member.preferred_tts_uid and db_member.preferred_tts:
            current_source = db_member.preferred_tts.source

        self.tts_source_var = ctk.StringVar(value=current_source)
        valid_sources = SOURCES[:]
        if not self.config.get(section="ELEVENLABS", option="api_key"):
            valid_sources.remove(SOURCE_11L)
        self.tts_source_dropdown = ctk.CTkOptionMenu(self, values=valid_sources, variable=self.tts_source_var, command=self._update_voicelist)

        voices = self.tts[current_source].get_voices()
        self.tts_options = list(voices.keys())
        self.tts_dropdown = ctk.CTkOptionMenu(
            self, values=self.tts_options
        )

        if self.member.preferred_tts_uid and self.member.preferred_tts_uid in voices.values():
            for k, v in voices.items():
                if v == self.member.preferred_tts_uid:
                    self.tts_dropdown.set(value=k)
                    break
        else:
            self.tts_dropdown.set(value=self.tts_options[0])

        self.tts_source_dropdown.pack(pady=(5, 20))
        self.tts_dropdown.pack(pady=(5, 20))

        self.test_button = ctk.CTkButton(self, text="Preview", command=self.test_tts)
        self.test_button.pack(pady=10)

        self.save_button = ctk.CTkButton(self, text="Save", command=self.save_changes)
        self.save_button.pack(pady=10)


    def _update_voicelist(self, choice):
        voices = self.tts[choice].get_voices()
        self.tts_options = list(voices.keys())
        self.tts_dropdown.configure(values=self.tts_options)
        if self.member.preferred_tts_uid and self.member.preferred_tts_uid in voices.values():
            for k, v in voices.items():
                if v == self.member.preferred_tts_uid:
                    self.tts_dropdown.set(value=k)
                    break
        else:
            self.tts_dropdown.set(value=self.tts_options[0])


    def test_tts(self):
        voice_id = self.tts[self.tts_source_var.get()].get_voices()[self.tts_dropdown.get()]
        self.tts[self.tts_source_var.get()].test_speak(voice_id = voice_id)


    def save_changes(self):
        new_tts = self.tts_dropdown.get()
        voices = self.tts[self.tts_source_var.get()].get_voices()
        voice_id = voices[new_tts]

        asyncio.create_task(update_tts(self.member, voice_id))
        logger.info(f"Updated preferred_tts for {self.member.name} to {new_tts}")

    def close_popup(self):
        MemberEditCard.open_popup = None
        self.destroy()

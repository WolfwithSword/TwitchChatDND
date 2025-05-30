import asyncio
from io import BytesIO

import customtkinter as ctk
import requests
from PIL import Image

from custom_logger.logger import logger
from data import Member
from data.member import create_or_get_member, fetch_member, update_tts, delete_member
from helpers.constants import TTS_SOURCE
from helpers.instance_manager import get_config
from helpers.utils import run_coroutine_sync, try_get_cache
from tts import get_tts
from chatdnd.events.chat_events import chat_on_party_modify
from chatdnd.events.ui_events import ui_refresh_user, ui_request_member_refresh, on_external_member_change
from chatdnd.events.session_events import session_refresh_member
from twitch.chat import ChatController
from ui.widgets.CTkPopupMenu.custom_popupmenu import CTkContextMenu, ContextMenuTypes
from ui.widgets.CTkScrollableDropdown.ctk_scrollable_dropdown import CTkScrollableDropdown


class MemberCard(ctk.CTkFrame):

    # fmt: skip
    def __init__(
        self,
        parent,
        member: Member,
        context_menu: CTkContextMenu,
        chat_ctrl: ChatController,
        width=160,
        height=200,
        textsize=12,
        *args,
        **kwargs,
    ):
        super().__init__(parent, width=width, height=height, *args, **kwargs)
        self.member: Member = member
        self.chat_ctrl = chat_ctrl
        self.bg_image = None
        self.bg_label = None
        self.width = width
        self.height = height
        self.textsize = textsize
        self.context_menu = context_menu
        self.grid_propagate(False)

        self.bg_label = None

        self.create_card()

        self.bind("<Button-1>", self.open_edit_popup)
        self.configure(cursor="hand2")

        ui_refresh_user.addListener(self._refresh_member)

    def create_card(self):
        self.setup_pfp()

        name_label = ctk.CTkLabel(
            self,
            text=self.member.name.upper(),
            font=("Arial", self.textsize),
            wraplength=self.width - 10,
        )
        name_label.grid(row=2, column=0, sticky="s", padx=5, pady=(2, 10))
        name_label.bind("<Button-1>", self.open_edit_popup)

    def show_ctx_menu(self, event):
        try:
            if self.context_menu.type != ContextMenuTypes.MEMBER_CARD:
                self.context_menu.clear_contents()
                self.context_menu.add_command(label="Add to party", command=lambda: chat_on_party_modify.trigger([self.member, False]))
                self.context_menu.add_command(label="Kick from party", command=lambda: chat_on_party_modify.trigger([self.member, True]))
                self.context_menu.add_separator()
                self.context_menu.add_command(label="Refresh", command=lambda: ui_request_member_refresh.trigger([self.member]))
                self.context_menu.add_separator()
                self.context_menu.add_command(label="Delete", command=self.delete_user)
            else:
                children = self.context_menu.prep_for_rewrite()
                children[0].configure(command=lambda: chat_on_party_modify.trigger([self.member, False]))
                children[1].configure(command=lambda: chat_on_party_modify.trigger([self.member, True]))
                children[3].configure(command=lambda: ui_request_member_refresh.trigger([self.member]))
                children[5].configure(command=self.delete_user)
            self.context_menu.type = ContextMenuTypes.MEMBER_CARD
            self.context_menu.after(50, self.context_menu.popup(event.x_root, event.y_root))
        finally:
            self.context_menu.grab_release()

    def delete_user(self):
        chat_on_party_modify.trigger([self.member, True])
        asyncio.create_task(delete_member(self.member))
        on_external_member_change.trigger()

    def get_pfp_url_cache(self, url):
        response = None
        key = f"{url}.member.pfp"

        cache = try_get_cache('default')
        if cache:
            response = cache.get(key=key, default=None)
            logger.debug(f"Fetched {key} from cache")
            if response:
                return response

        response = requests.get(url, timeout=10)
        if response and cache:
            config = get_config('default')
            cache.set(
                key=key, expire=config.getint(section="CACHE", option="pfp_cache_expiry", fallback=7 * 24 * 60 * 60 * 2), value=response
            )
        return response

    def setup_pfp(self):
        if not self.winfo_exists():
            return
        try:
            url = self.member.pfp_url
            response = self.get_pfp_url_cache(url)
            img_data = response.content
            img = Image.open(BytesIO(img_data))

            resize_method = Image.Resampling.LANCZOS
            img = img.resize((self.width, self.height), resize_method)

            self.bg_image = ctk.CTkImage(img, img, (self.width, self.width))

            if not self.bg_label:
                self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
                self.bg_label.grid(row=0, column=0, sticky="nsew", rowspan=2)
            else:
                self.bg_label.configure(image=self.bg_image)
        except Exception as e:
            logger.warning(f"Could not fetch image for {self.member}. {e}")
            self.bg_image = None
            if not self.bg_label:
                self.bg_label = ctk.CTkLabel(self, text="No Image", font=("Arial", self.textsize))
                self.bg_label.grid(row=0, column=0, sticky="nsew")
            else:
                self.bg_label.configure(image=self.bg_image)
        self.bg_label.bind("<Button-1>", self.open_edit_popup)
        self.bg_label.bind("<Button-3>", self.show_ctx_menu)

    def _refresh_member(self, user):
        if not user or user.display_name.upper() != self.member.name.upper():
            return
        member = run_coroutine_sync(create_or_get_member(name=user.display_name, pfp_url=user.profile_image_url))
        if member and self.member.name == member.name and self.member.pfp_url != member.pfp_url:
            self.member = member
            self.setup_pfp()
            session_refresh_member.trigger([member])

    def open_edit_popup(self, event=None):
        self.member = run_coroutine_sync(fetch_member(name=self.member.name))
        MemberEditCard(self.member)

    def destroy(self):
        ui_refresh_user.removeListener(self._refresh_member)
        super().destroy()


class MemberEditCard(ctk.CTkToplevel):
    open_popup = None

    def __init__(self, member: Member):
        if MemberEditCard.open_popup is not None:
            MemberEditCard.open_popup.focus_set()
            return
        super().__init__()
        MemberEditCard.open_popup = self
        self.member: Member = member
        self.tts_options = []
        self.title(f"Edit {self.member.name.upper()}")
        self.geometry("400x400")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close_popup)

        self.attributes("-topmost", True)

        self.create_widgets()
        # self.deiconify()

    def create_widgets(self):
        # TODO add stuff, make pretty, idk
        label1 = ctk.CTkLabel(self, text="TTS Voice Source:")
        label1.pack(pady=(20, 5))

        self.label = ctk.CTkLabel(self, text="TTS Voice:")
        self.label.pack(pady=(20, 5))

        current_source = TTS_SOURCE.SOURCE_LOCAL.value

        db_member = run_coroutine_sync(fetch_member(name=self.member.name))
        if db_member.preferred_tts_uid and db_member.preferred_tts:
            current_source = db_member.preferred_tts.source

        self.tts_source_var = ctk.StringVar(value=current_source)

        valid_sources = [source.value for source in TTS_SOURCE][:]
        config = get_config('default')
        if not config.get(section="ELEVENLABS", option="api_key"):
            valid_sources.remove(TTS_SOURCE.SOURCE_11L.value)
        self.tts_source_dropdown = ctk.CTkOptionMenu(
            self,
            variable=self.tts_source_var,

        )

        voices = get_tts(TTS_SOURCE(current_source)).get_voices()

        self.tts_drop_frame = CTkScrollableDropdown(self.tts_source_dropdown, values=valid_sources, command=self._update_voicelist, height=300, width=160, alpha=1, button_height=30)
        self.tts_options = list(voices.keys())
        self.tts_dropdown = ctk.CTkOptionMenu(self)

        self.tts_voice_drop_frame = CTkScrollableDropdown(self.tts_dropdown, values=self.tts_options, width=425, height=385, alpha=1, justify="left", button_height=30)

        if self.member.preferred_tts_uid and self.member.preferred_tts_uid in voices.values():
            for k, v in voices.items():
                if v == self.member.preferred_tts_uid:
                    self.tts_dropdown.set(value=k)
                    break
        else:
            self.tts_dropdown.set(value=self.tts_options[0])

        self.tts_source_dropdown.pack(padx=10, pady=(5, 20))
        self.tts_dropdown.pack(padx=10, pady=(5, 20))

        self.test_button = ctk.CTkButton(self, text="Preview", command=self.test_tts)
        self.test_button.pack(pady=10)

        self.save_button = ctk.CTkButton(self, text="Save", command=self.save_changes)
        self.save_button.pack(pady=10)

        num_sessions_label = ctk.CTkLabel(self, text=f"Number of Sessions: {self.member.num_sessions}")
        num_sessions_label.pack(pady=(20, 5))

    def _update_voicelist(self, choice):
        voices = get_tts(TTS_SOURCE(choice)).get_voices()
        self.tts_options = list(voices.keys())
        self.tts_voice_drop_frame.configure(values=self.tts_options)
        if self.member.preferred_tts_uid and self.member.preferred_tts_uid in voices.values():
            for k, v in voices.items():
                if v == self.member.preferred_tts_uid:
                    self.tts_dropdown.set(value=k)
                    break
        else:
            self.tts_dropdown.set(value=self.tts_options[0])

        self.tts_source_dropdown.set(value=choice)
        self.tts_source_var.set(value=choice)

    def test_tts(self):
        tts = get_tts(TTS_SOURCE(self.tts_source_var.get()))
        voice_id = tts.get_voices()[self.tts_dropdown.get()]
        tts.test_speak(voice_id=voice_id)

    def save_changes(self):
        new_tts = self.tts_dropdown.get()
        voices = get_tts(TTS_SOURCE(self.tts_source_var.get())).get_voices()
        voice_id = voices[new_tts]

        asyncio.create_task(update_tts(self.member, voice_id))
        logger.info(f"Updated preferred_tts for {self.member.name} to {new_tts}")

    def close_popup(self):
        MemberEditCard.open_popup = None
        self.destroy()

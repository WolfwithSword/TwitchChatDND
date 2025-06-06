from logging import getLogger
import webbrowser
import re
import os

from PIL import Image
from win11toast import notify

import customtkinter as ctk
from CTkListbox import *
from CTkToolTip import CTkToolTip

from helpers.instance_manager import get_config
from helpers.utils import run_coroutine_sync, check_for_updates, get_resource_path
from helpers.constants import TTS_SOURCE
from twitch.utils import TwitchUtils
from tts import get_tts
from data.voices import delete_voice
from data.member import remove_tts

logger = getLogger("ChatDND")

from chatdnd.events.ui_events import (
    ui_settings_twitch_channel_update_event,
    ui_on_startup_complete,
    ui_request_floating_notif,
    ui_fetch_update_check_event,
    ui_remove_floating_notif,
    ui_settings_twitch_auth_update_event
)

from chatdnd.events.chat_events import chat_bot_on_connect

from chatdnd.events.twitchutils_events import twitchutils_twitch_on_connect_event
from chatdnd.events.tts_events import (
    request_elevenlabs_connect,
    on_elevenlabs_connect,
    on_elevenlabs_test_speak,
    on_elevenlabs_subscription_update,
)

from ui.widgets.CTkFloatingNotifications import NotifyType


class SettingsTab:
    # TODO Someone, please, clean this POS up. I'm begging. Nvm it's actually sorta clean, not really, but good enough

    def __init__(self, parent, twitch_utils: TwitchUtils):
        self.parent = parent
        self.twitch_utils = twitch_utils
        config = get_config("default")

        self.startup = True

        header_font = ctk.CTkFont(family="Helvetica", size=20, weight="bold")
        bold_font = ctk.CTkFont(weight="bold")

        row = 0
        ######### ChatDND #########
        column = 0
        cdnd_label = ctk.CTkLabel(self.parent, text="ChatDND", font=header_font)
        cdnd_label.grid(row=row, column=column, padx=10, pady=(30, 2), sticky="ew")
        column += 1
        self.utd_label = ctk.CTkLabel(self.parent, text="Up To Date")
        self.utd_label.grid(row=row, column=column, padx=10, pady=(30, 2))
        column += 1
        check_update_button = ctk.CTkButton(
            self.parent,
            height=30,
            text="Check for Updates",
            command=self._check_for_updates,
        )
        check_update_button.grid(row=row, column=column, padx=10, pady=(30, 2))

        img = Image.open(get_resource_path("../../images/logo.png", from_resources=True))
        resize_method = Image.Resampling.LANCZOS
        img = img.resize((256, int(128 * 1.5)), resize_method)
        logo_image = ctk.CTkImage(img, img, (256, int(128 * 1.5)))
        logo_label = ctk.CTkLabel(self.parent, image=logo_image, text="")
        logo_label.grid(row=0, column=5, sticky="ne", rowspan=2, columnspan=3)
        logo_label.bind(
            "<Button-1>",
            lambda e: webbrowser.open("https://github.com/WolfwithSword/TwitchChatDND", new=0, autoraise=True),
        )
        logo_label.bind("<Enter>", lambda e: logo_label.configure(cursor="hand2"))
        logo_label.bind("<Leave>", lambda e: logo_label.configure(cursor=""))

        CTkToolTip(logo_label, message="Open ChatDnD Page", delay=0.3, corner_radius=50)
        ###########################

        row += 1
        ######### Twitch ##########
        column = 0
        label = ctk.CTkLabel(self.parent, text="Twitch Bot", font=header_font)
        label.grid(row=row, column=column, padx=10, pady=(30, 2), sticky="ew")
        column += 1
        self.t_con_label = ctk.CTkLabel(self.parent, text="Twitch Disconnected", text_color="red")
        self.t_con_label.grid(row=row, column=column, padx=10, pady=(30, 2))
        column += 1
        self.chat_con_label = ctk.CTkLabel(self.parent, text="Chat Disconnected", text_color="red")
        self.chat_con_label.grid(row=row, column=column, padx=10, pady=(30, 2))
        chat_bot_on_connect.addListener(self._update_bot_connection)
        column = 0
        row += 1

        button = ctk.CTkButton(self.parent, height=30, text="Save", command=self._update_bot_settings)
        button.grid(row=row, column=column, padx=10, pady=(20, 10))
        row += 1
        reauth_button = ctk.CTkButton(self.parent, height=30, text="ReAuth", command=self._reauth_bot)
        reauth_button.grid(row=row, column=column, padx=10, pady=(20, 10))
        row -= 1
        column += 1
        chan_label = ctk.CTkLabel(self.parent, text="Channel")
        chan_label.grid(row=row, column=column, padx=(10, 10), pady=(10, 2))
        column += 1
        prefix_label = ctk.CTkLabel(self.parent, text="Command Prefix")
        prefix_label.grid(row=row, column=column, padx=(10, 10), pady=(10, 2))
        column += 1
        join_label = ctk.CTkLabel(self.parent, text="Join Command")
        join_label.grid(row=row, column=column, padx=(10, 10), pady=(10, 2))
        column += 1
        say_label = ctk.CTkLabel(self.parent, text="Speak Command")
        say_label.grid(row=row, column=column, padx=(10, 10), pady=(10, 2))

        row += 1
        column = 1
        self.twitch_channel = ctk.CTkLabel(
            self.parent,
            width=180,
            height=30,
            text=("None" if not self.twitch_utils.channel else self.twitch_utils.channel.display_name),
            font=bold_font,
        )
        self.twitch_channel.configure(justify="center")

        self.twitch_channel.grid(row=row, column=column, padx=(20, 20), pady=(2, 20))
        column += 1
        self.prefix_var = ctk.StringVar(value=config.get(section="BOT", option="prefix", fallback="!").strip()[0])
        prefix_options = ctk.CTkSegmentedButton(self.parent, values=["!", "~", "+", "&"], variable=self.prefix_var)
        prefix_options.grid(row=row, column=column, padx=(20, 20), pady=(2, 20))
        column += 1
        self.join_cmd_var = ctk.StringVar(value=config.get(section="BOT", option="join_command", fallback=""))
        join_cmd_entry = ctk.CTkEntry(
            self.parent,
            width=100,
            height=30,
            border_width=1,
            fg_color="white",
            placeholder_text="join",
            text_color="black",
            textvariable=self.join_cmd_var,
        )
        join_cmd_entry.grid(row=row, column=column, padx=(20, 20), pady=(2, 20))
        join_cmd_entry.configure(justify="center")
        column += 1
        self.speak_cmd_var = ctk.StringVar(value=config.get(section="BOT", option="speak_command", fallback=""))
        speak_cmd_entry = ctk.CTkEntry(
            self.parent,
            width=100,
            height=30,
            border_width=1,
            fg_color="white",
            placeholder_text="say",
            text_color="black",
            textvariable=self.speak_cmd_var,
        )
        speak_cmd_entry.grid(row=row, column=column, padx=(20, 20), pady=(2, 20))
        speak_cmd_entry.configure(justify="center")

        twitchutils_twitch_on_connect_event.addListener(self._update_twitch_connect)

        row += 1
        column = 3
        voice_cmd_label = ctk.CTkLabel(self.parent, text="Set Voice Command")
        voice_cmd_label.grid(row=row, column=column, padx=(10, 10), pady=(10, 2))
        column += 1
        voices_cmd_label = ctk.CTkLabel(self.parent, text="List Voices Command")
        voices_cmd_label.grid(row=row, column=column, padx=(10, 10), pady=(10, 2))
        row += 1
        column -= 1
        self.voice_cmd_var = ctk.StringVar(value=config.get(section="BOT", option="voice_command", fallback=""))
        voice_cmd_entry = ctk.CTkEntry(
            self.parent,
            width=100,
            height=30,
            border_width=1,
            fg_color="white",
            placeholder_text="join",
            text_color="black",
            textvariable=self.voice_cmd_var,
        )
        voice_cmd_entry.grid(row=row, column=column, padx=(20, 20), pady=(2, 20))
        voice_cmd_entry.configure(justify="center")
        column += 1
        self.listvoice_cmd_var = ctk.StringVar(value=config.get(section="BOT", option="voices_command", fallback=""))
        voices_cmd_entry = ctk.CTkEntry(
            self.parent,
            width=100,
            height=30,
            border_width=1,
            fg_color="white",
            placeholder_text="say",
            text_color="black",
            textvariable=self.listvoice_cmd_var,
        )
        voices_cmd_entry.grid(row=row, column=column, padx=(20, 20), pady=(2, 20))
        voices_cmd_entry.configure(justify="center")

        ########################

        ####### Web Srv ########
        row += 1
        column = 0
        label_web = ctk.CTkLabel(self.parent, text="Browser Source", anchor="w", font=header_font)
        label_web.grid(row=row, column=column, padx=10, pady=(30, 10))
        row += 1
        button_websrv = ctk.CTkButton(self.parent, height=30, text="Save", command=self._update_websrv_settings)
        button_websrv.grid(row=row, column=column, padx=10, pady=(20, 10))

        column += 1
        self.label_bs_var = ctk.StringVar(value=f"http://localhost:{config.get(section="SERVER", option='port', fallback='5000')}/overlay")
        label_bs = ctk.CTkEntry(self.parent, textvariable=self.label_bs_var, state="readonly", width=190)
        label_bs.grid(row=row, column=column, padx=(10, 2), pady=(10, 2))

        def _copy_web_clipboard():
            self.parent.clipboard_clear()
            self.parent.clipboard_append(label_bs.get())

        button_web = ctk.CTkButton(self.parent, width=30, height=30, text="Copy", command=_copy_web_clipboard)
        column += 1
        button_web.grid(row=row, column=column, padx=(2, 10), pady=(10, 2), sticky="w")

        column += 1
        port_label = ctk.CTkLabel(self.parent, text="Port")
        port_label.grid(row=row, column=column, padx=(10, 10), pady=(10, 2))

        row += 1
        self.port_var = ctk.StringVar(value=config.get(section="SERVER", option="port", fallback="5000"))
        self.port_var.trace_add("write", self._validate_port)
        port_entry = ctk.CTkEntry(
            self.parent,
            width=100,
            height=30,
            border_width=1,
            fg_color="white",
            placeholder_text="5000",
            text_color="black",
            textvariable=self.port_var,
        )
        port_entry.grid(row=row, column=column, padx=(20, 20), pady=(2, 20))
        port_entry.configure(justify="center")

        ######### 11L TTS ##########
        row += 1
        column = 0
        label_tts = ctk.CTkLabel(self.parent, text="ElevenLabs TTS", anchor="w", font=header_font)
        label_tts.grid(row=row, column=column, padx=10, pady=(40, 10))
        column += 1
        self.e11labs_con_label = ctk.CTkLabel(self.parent, text="ElevenLabs Disconnected", text_color="red")
        self.e11labs_con_label.grid(row=row, column=column, padx=10, pady=(30, 2))

        column += 1
        self.e11labs_usage_label = ctk.CTkLabel(self.parent, text="")
        self.e11labs_usage_label.grid(row=row, column=column, padx=10, pady=(30, 2))

        row += 1
        column = 0
        button_el = ctk.CTkButton(self.parent, height=30, text="Save", command=self._update_el_settings)
        button_el.grid(row=row, column=column, padx=10, pady=(20, 10))
        column += 1
        el_api_label = ctk.CTkLabel(self.parent, text="API Key")
        el_api_label.grid(row=row, column=column, padx=(10, 10), pady=(10, 2))
        column += 1
        el_voices_label = ctk.CTkLabel(self.parent, text="ElevenLabs Added Voices")
        el_voices_label.grid(row=row, column=column, padx=(10, 10), pady=(10, 2))

        column = 1
        row += 1
        self.el_api_key_var = ctk.StringVar(value=config.get(section="ELEVENLABS", option="api_key", fallback=""))
        el_api_key_entry = ctk.CTkEntry(
            self.parent,
            width=180,
            height=30,
            border_width=1,
            fg_color="white",
            placeholder_text="API Key",
            text_color="black",
            textvariable=self.el_api_key_var,
        )
        el_api_key_entry.configure(justify="center", show="*")
        el_api_key_entry.grid(row=row, column=column, padx=(20, 20), pady=(2, 20), sticky="n")

        self.e11_voices = CTkListbox(self.parent, width=450, height=200, command=self._on_voice_option_select)

        column += 1
        self.e11_voices.grid(row=row, column=column, columnspan=3)
        column += 3

        # could undo some of these self's if in a method?
        self.add_import_button = ctk.CTkButton(self.parent, height=30, text="Import All", command=self._import_e11_all)
        self.add_import_button.grid(row=row, column=column, padx=10, pady=(2, 10), sticky="n")

        self.add_v_button = ctk.CTkButton(self.parent, height=30, text="Add Voice", command=self.open_edit_popup)
        self.add_v_button.grid(row=row, column=column, padx=10, pady=(52, 10), sticky="n")
        self.del_v_button = ctk.CTkButton(
            self.parent,
            height=30,
            text="Remove Voice",
            fg_color="#b1363d",
            hover_color="#772429",
            command=self._delete_voice,
        )
        self.del_v_button.grid(row=row, column=column, padx=10, pady=(92, 10), sticky="n")
        self.preview_v_button = ctk.CTkButton(
            self.parent,
            height=30,
            text="Preview Voice",
            command=self._preview_e11_voice,
        )
        self.preview_v_button.grid(row=row, column=column, padx=10, pady=(168, 10), sticky="n")

        column = 1

        el_warn_val_label = ctk.CTkLabel(self.parent, text="Warning Limit")
        el_warn_val_label.grid(row=row, column=column, padx=(10, 10), pady=(62, 2), sticky="n")

        self.el_warning_var = ctk.StringVar(value=config.get(section="ELEVENLABS", option="usage_warning", fallback="500"))
        self.el_warning_var.trace_add("write", self._validate_el_warning_numeric)
        el_warning_entry = ctk.CTkEntry(
            self.parent,
            width=180,
            height=30,
            border_width=1,
            fg_color="white",
            placeholder_text="500",
            text_color="black",
            textvariable=self.el_warning_var,
        )
        el_warning_entry.configure(justify="center")
        el_warning_entry.grid(row=row, column=column, padx=(20, 20), pady=(42, 20))

        on_elevenlabs_connect.addListener(self._update_elevenlabs_connection)
        on_elevenlabs_subscription_update.addListener(self._update_elevenlabs_usage)
        request_elevenlabs_connect.trigger()
        ui_on_startup_complete.addListener(self.finish_startup)
        ui_fetch_update_check_event.addListener(self._update_check_result)

    def _validate_el_warning_numeric(self, *data):
        val = self.el_warning_var.get()

        val = self._validate_is_number(val, _min=1)
        if val != self.el_warning_var.get():
            self.el_warning_var.set(val)

    def _validate_port(self, *data):
        val = self.port_var.get()

        val = self._validate_is_number(val, "5000", _min=1000, _max=65535)
        if val != self.port_var.get():
            self.port_var.set(val)

    def _validate_is_number(self, value: str, val_if_empty: str = "", _min=0, _max=999999999):
        if not val_if_empty:
            val_if_empty = value
        if value is None or value.strip() == "":
            return val_if_empty
        elif value.isdigit():
            if not _min <= int(value) <= _max:
                if int(value) >= _max:
                    value = _max
                elif int(value) <= _min:
                    value = _min
                value = str(value)
            return value
        value = re.sub(r"[^0-9]", "", value)
        if not _min <= int(value) <= _max:
            if int(value) >= _max:
                value = _max
            elif int(value) <= _min:
                value = _min
            value = str(value)
        return value

    def finish_startup(self):
        self.startup = False

    def open_edit_popup(self, event=None):
        AddVoiceCard(self._update_voice_list)

    def _on_voice_option_select(self, option):
        if option:
            self.preview_v_button.configure(state="normal")
            if self.e11_voices.size() > 1:
                self.del_v_button.configure(state="normal")
            else:
                self.del_v_button.configure(state="disabled")
        else:
            self.del_v_button.configure(state="disabled")
            self.preview_v_button.configure(state="disabled")

    def _import_e11_all(self):
        client = get_tts(TTS_SOURCE.SOURCE_11L)
        success = client.import_all(True)
        if success:
            self._update_voice_list()

    def _preview_e11_voice(self):
        option = self.e11_voices.get()
        if not option:
            return
        client = get_tts(TTS_SOURCE.SOURCE_11L)
        if uid := client.get_voices()[option]:
            on_elevenlabs_test_speak.trigger(["Hello there. How are you?", uid])

    def _update_voice_list(self):
        client = get_tts(TTS_SOURCE.SOURCE_11L)
        if self.e11_voices.size():
            self.e11_voices.selection_clear()
            while self.e11_voices.size():
                self.e11_voices.deactivate("END")
                self.e11_voices.delete("END")

        for k in client.get_voices().keys():  # pylint: disable=consider-iterating-dictionary
            self.e11_voices.insert("END", option=k)
        self.del_v_button.configure(state="disabled")
        self.preview_v_button.configure(state="disabled")

    def _delete_voice(self):
        if self.e11_voices.size() <= 1:
            return
        option = self.e11_voices.get()
        client = get_tts(TTS_SOURCE.SOURCE_11L)
        result1 = None
        if uid := client.get_voices()[option]:
            run_coroutine_sync(remove_tts(voice_id=uid))
            result1 = run_coroutine_sync(delete_voice(uid=uid, source=TTS_SOURCE.SOURCE_11L))
        if result1:
            self._update_voice_list()

    def _update_websrv_settings(self):
        config = get_config("default")
        config.set(section="SERVER", option="port", value=str(self.port_var.get()))
        config.write_updates()
        ui_request_floating_notif.trigger(
            [
                "Please restart the application to apply port changes!",
                NotifyType.WARNING,
                {"duration": 20000},
            ]
        )
        self.label_bs_var.set(f"http://localhost:{config.get(section="SERVER", option='port', fallback='5000')}/overlay")
        # TODO Look into if we can restart task for webserver

    def _update_el_settings(self):
        config = get_config("default")
        config.set(section="ELEVENLABS", option="api_key", value=str(self.el_api_key_var.get()))
        config.set(
            section="ELEVENLABS",
            option="usage_warning",
            value=str(self.el_warning_var.get()),
        )
        config.write_updates()
        request_elevenlabs_connect.trigger()

    def _reauth_bot(self):
        file_path = get_resource_path("../../user_token.json", from_root=True)
        logger.info(f"Attempting to remove twitch auth from: {file_path}")
        if os.path.isfile(file_path):
            os.remove(file_path)
        ui_settings_twitch_auth_update_event.trigger()

    def _update_bot_settings(self):
        self.chat_con_label.configure(text="Chat Connecting...", text_color="yellow")
        config = get_config("default")
        config.set(section="BOT", option="prefix", value=str(self.prefix_var.get()))
        config.set(
            section="BOT",
            option="speak_command",
            value=self.speak_cmd_var.get().strip(),
        )
        config.set(section="BOT", option="join_command", value=self.join_cmd_var.get().strip())
        config.set(
            section="BOT",
            option="voice_command",
            value=self.voice_cmd_var.get().strip(),
        )
        config.set(
            section="BOT",
            option="voices_command",
            value=self.listvoice_cmd_var.get().strip(),
        )
        config.write_updates()
        ui_settings_twitch_channel_update_event.trigger([True, self.twitch_utils, 5])

    def _update_elevenlabs_usage(self, count: int, limit: int):
        self.e11labs_usage_label.configure(text=f"{limit-count}/{limit} | {abs(((limit-count)*100)//limit)}% Remaining")
        config = get_config("default")
        if limit - count < config.getint(section="ELEVENLABS", option="usage_warning", fallback=500):
            ui_request_floating_notif.trigger(
                [
                    "ElevenLabs credit usage warning!",
                    NotifyType.WARNING,
                    {"bg_color": "#202020", "text_color": "#b0b0b0", "duration": 10000},
                ]
            )
            # TODO check that current OS is windows for this
            # TODO if multi-platform, setup a notifier package/module for crossplatform and call event to there
            notify(
                "ChatDnD",
                "Your available Elevenlabs character count is low",
                progress={
                    "title": "Elevenlabs Usage Warning",
                    "status": "Usage Warning",
                    "value": str((limit - count) / limit),
                    "valueStringOverride": f"{limit-count}/{limit} Characters",
                },
                duration="long",
                buttons=[
                    {
                        "activationType": "protocol",
                        "arguments": "https://elevenlabs.io/app/subscription",
                        "content": "See Plans",
                    },
                    {
                        "activationType": "protocol",
                        "arguments": "https://elevenlabs.io/app/usage",
                        "content": "View Usage",
                    },
                ],
            )

    def _update_elevenlabs_connection(self, status: bool):
        if status:
            self.e11labs_con_label.configure(text="ElevenLabs Connected", text_color="green")
            self._update_voice_list()
            self.add_v_button.configure(state="normal")
            self.add_import_button.configure(state="normal")
            if not self.startup:
                ui_request_floating_notif.trigger(["ElevenLabs connected!", NotifyType.INFO, {"name": "elevenlabs_connect"}])
                ui_remove_floating_notif.trigger(["elevenlabs_disconnect", "contains"])
        else:
            self.e11labs_con_label.configure(text="ElevenLabs Disconnected", text_color="red")
            self.add_v_button.configure(state="disabled")
            self.add_import_button.configure(state="disabled")
            if self.e11_voices.size():
                self.e11_voices.selection_clear()
                while self.e11_voices.size():
                    self.e11_voices.deactivate("END")
                    self.e11_voices.delete("END")
            self.del_v_button.configure(state="disabled")
            self.preview_v_button.configure(state="disabled")
            self.parent.focus()
            config = get_config("default")
            if config.get(section="ELEVENLABS", option="api_key") and not self.startup:
                ui_request_floating_notif.trigger(["ElevenLabs disconnected!", NotifyType.WARNING, {"name": "elevenlabs_disconnect"}])
                ui_remove_floating_notif.trigger(["elevenlabs_connect", "contains"])

    def _update_bot_connection(self, status: bool):
        if status:
            self.chat_con_label.configure(text="Chat Connected", text_color="green")
            if not self.startup:
                ui_request_floating_notif.trigger(["Twitch Chatbot connected!", NotifyType.INFO, {"name": "twitch_connect"}])
                ui_remove_floating_notif.trigger(["twitch_disconnect", "contains"])
            self.twitch_channel.configure(text=("None" if not self.twitch_utils.channel else self.twitch_utils.channel.display_name))
        else:
            self.chat_con_label.configure(text="Chat Disconnected", text_color="red")
            self.twitch_channel.configure(text="None")
            if not self.startup:
                ui_request_floating_notif.trigger(["Twitch Chatbot disconnected!", NotifyType.WARNING, {"name": "twitch_disconnect"}])
                ui_remove_floating_notif.trigger(["twitch_connect", "contains"])
            self.parent.focus()

    def _update_twitch_connect(self, status: bool, twitchutils=None):
        if status:
            self.t_con_label.configure(text="Twitch Connected", text_color="green")
            # Remove notif if open
            ui_remove_floating_notif.trigger(["twitch_auth", "equals"])
        else:
            self.t_con_label.configure(text="Twitch Disconnected", text_color="red")
            self.parent.focus()

    def _check_for_updates(self):
        ui_fetch_update_check_event.trigger([check_for_updates(), True])

    def _update_check_result(self, value, open_page: bool = False):
        if value:
            new_version = value.split("/").pop()
            ui_request_floating_notif.trigger(
                [
                    f"Update available [{new_version}]!",
                    NotifyType.SUCCESS,
                    {"duration": 10000},
                ]
            )
            self.utd_label.configure(text=f"Update Available [{new_version}]", text_color="orange")
            if open_page:
                webbrowser.open(value, new=2)


class AddVoiceCard(ctk.CTkToplevel):
    open_popup = None

    def __init__(self, update_list_callback: callable):
        if AddVoiceCard.open_popup is not None:
            AddVoiceCard.open_popup.focus_set()
            return

        super().__init__()
        AddVoiceCard.open_popup = self
        self.update_list_callback = update_list_callback
        self.title("Add new ElevenLabs Voice")
        self.geometry("400x400")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close_popup)

        self.attributes("-topmost", True)
        self.create_widgets()

    def create_widgets(self):
        label1 = ctk.CTkLabel(self, text="ElevenLabs Voice Id:")
        label1.pack(pady=(20, 5))

        self.voice_id_var = ctk.StringVar()
        self.voice_id_input = ctk.CTkEntry(self, width=160, height=30, textvariable=self.voice_id_var)
        self.voice_id_input.pack(pady=(10, 10))

        self.label_warn = ctk.CTkLabel(self, text="", text_color="red")
        self.label_warn.pack(pady=10)

        self.save_button = ctk.CTkButton(self, text="Add", command=self.save_changes)
        self.save_button.pack(pady=10)

    def save_changes(self):
        elvoice = get_tts(TTS_SOURCE.SOURCE_11L).get_voice_object(voice_id=self.voice_id_var.get(), run_sync_always=True)
        if elvoice:
            self.close_popup()
        else:
            self.label_warn.configure(text="Voice Id not found!")
            # keep open and change label to error

    def close_popup(self):
        AddVoiceCard.open_popup = None
        self.update_list_callback()
        self.destroy()

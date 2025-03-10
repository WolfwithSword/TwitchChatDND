import customtkinter as ctk

from _version import __version__ as app_version
from chatdnd import SessionManager
from chatdnd.events.ui_events import ui_request_floating_notif
from custom_logger.logger import logger
from helpers import TCDNDConfig as Config
from helpers.utils import get_resource_path
from twitch.chat import ChatController
from twitch.utils import TwitchUtils
from ui.tabs.home import HomeTab
from ui.tabs.settings import SettingsTab
from ui.tabs.users import UsersTab
from ui.widgets import CTkScrollableTabView
from ui.widgets.CTkFloatingNotifications import NotificationManager, NotifyType

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class DesktopApp(ctk.CTk):

    def __init__(
        self,
        session_mgr: SessionManager,
        chat_ctrl: ChatController,
        config: Config,
        twitch_utils: TwitchUtils,
    ):
        super().__init__()
        self.running = True
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.resizable(False, False)
        self.config: Config = config
        self.twitch_utils = twitch_utils
        self.session_mgr = session_mgr
        self.chat_ctrl = chat_ctrl
        if app_version and app_version.startswith("v"):
            version_for_title = app_version[1:]
        else:
            version_for_title = app_version
        self.title(f"Twitch Chat DND Manager - v.{version_for_title}")

        icon_path = get_resource_path("../../images/logo.ico", from_resources=True)
        self.iconbitmap(icon_path)

        self.geometry("1200x750")

        self.tabview = CTkScrollableTabView(self, anchor="w")
        self.tabview.pack(fill="both", expand=True)

        self.notification_manager = NotificationManager(self)
        ui_request_floating_notif.addListener(self._show_floating_notif)

        self._setup_tabs()

    def _setup_tabs(self):

        home_tab = self.tabview.add("Home", scrollable=False)
        users_tab = self.tabview.add("Users", scrollable=False)
        settings_tab = self.tabview.add("Settings", scrollable=True)

        # TODO - see if we even need to pass in chat_ctrl, or if we can purely use my Events and triggers
        home = HomeTab(home_tab, self.chat_ctrl)
        users = UsersTab(users_tab, self.chat_ctrl)
        settings = SettingsTab(settings_tab, self.config, self.twitch_utils)
        assert all([home, users, settings])

    def button_callback(self):
        logger.info("Test")

    def on_close(self):
        logger.info("Shutting down...")
        self.running = False
        self.destroy()

    def _show_floating_notif(self, text: str, _type: NotifyType, data: dict = {}):
        if text and _type:
            if data is not None and isinstance(data, dict):
                data.setdefault("bg_color", "#202020")
                data.setdefault("text_color", "#b0b0b0")
                data.setdefault("duration", 6000)
                self.notification_manager.show_notification(text, _type, **data)

            else:
                self.notification_manager.show_notification(text, _type)

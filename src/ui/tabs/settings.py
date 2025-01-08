import customtkinter as ctk
from custom_logger.logger import logger

from helpers import TCDNDConfig as Config
from twitch.utils import TwitchUtils
from chatdnd.events.ui_events import *
from chatdnd.events.chat_events import *
from chatdnd.events.twitchutils_events import twitchutils_twitch_on_connect_event

class SettingsTab():
    # TODO Someone, please, clean this POS up. I'm begging. Nvm it's actually sorta clean, not really, but good enough

    def __init__(self, parent, config: Config, twitch_utils: TwitchUtils):
        self.parent=parent


        self.config = config
        self.twitch_utils = twitch_utils

        header_font = ctk.CTkFont(family="Helvetica", size=20, weight="bold")

        row=0
        ######### Twitch ##########
        column=0
        label = ctk.CTkLabel(self.parent, text="Twitch Bot", font=header_font)
        label.grid(row=row, column=column, padx=10, pady=(30,2), sticky="ew")
        column+=1
        self.t_con_label = ctk.CTkLabel(self.parent, text="Twitch Disconnected", text_color="red")
        self.t_con_label.grid(row=row, column=column, padx=10, pady=(30,2))
        column+=1
        self.chat_con_label = ctk.CTkLabel(self.parent, text="Chat Disconnected", text_color="red")
        self.chat_con_label.grid(row=row, column=column, padx=10, pady=(30,2))
        chat_bot_on_connect.addListener(self._update_bot_connection)
        column=0
        row+=1

        button = ctk.CTkButton(self.parent,height=30, text="Save", command=self._update_bot_settings)
        button.grid(row=row, column=column, padx=10, pady=(20,10))
        column+=1
        chan_label = ctk.CTkLabel(self.parent, text="Channel")
        chan_label.grid(row=row, column=column, padx=(10,10), pady=(10,2))
        column+=1
        prefix_label = ctk.CTkLabel(self.parent, text="Command Prefix")
        prefix_label.grid(row=row, column=column, padx=(10,10), pady=(10,2))
        column+=1
        join_label = ctk.CTkLabel(self.parent, text="Join Command")
        join_label.grid(row=row, column=column, padx=(10,10), pady=(10,2))
        column+=1
        say_label = ctk.CTkLabel(self.parent, text="Speak Command")
        say_label.grid(row=row, column=column, padx=(10,10), pady=(10,2))

        row+=1
        column=1
        self.channel_var = ctk.StringVar(value=self.config.get(section="TWITCH", option="channel", fallback=""))
        twitch_channel = ctk.CTkEntry(self.parent, width=180, height=30, border_width=1, fg_color="white", placeholder_text="Channel", text_color="black", textvariable=self.channel_var)
        twitch_channel.configure(justify="center")

        twitch_channel.grid(row=row, column=column, padx=(20,20), pady=(2, 20))
        column+=1  
        self.prefix_var = ctk.StringVar(value=self.config.get(section="BOT", option="prefix", fallback='!').strip()[0])
        prefix_options = ctk.CTkSegmentedButton(self.parent, values=['!', '~', '+', '&'], variable=self.prefix_var)
        prefix_options.grid(row=row, column=column, padx=(20,20), pady=(2, 20))
        column += 1
        self.join_cmd_var = ctk.StringVar(value=self.config.get(section="BOT", option="join_command", fallback=''))
        join_cmd_entry = ctk.CTkEntry(self.parent,  width=100, height=30, border_width=1, fg_color="white", placeholder_text="join", text_color="black", textvariable=self.join_cmd_var)
        join_cmd_entry.grid(row=row, column=column, padx=(20,20), pady=(2, 20))
        join_cmd_entry.configure(justify="center")
        column += 1
        self.speak_cmd_var = ctk.StringVar(value=self.config.get(section="BOT", option="speak_command", fallback=''))
        speak_cmd_entry = ctk.CTkEntry(self.parent,  width=100, height=30, border_width=1, fg_color="white", placeholder_text="say", text_color="black", textvariable=self.speak_cmd_var)
        speak_cmd_entry.grid(row=row, column=column, padx=(20,20), pady=(2, 20))
        speak_cmd_entry.configure(justify="center")

        twitchutils_twitch_on_connect_event.addListener(self._update_twitch_connect)

        ########################

        ####### Web Srv ########
        row+=1
        column=0
        label_web = ctk.CTkLabel(self.parent, text="Browser Source", anchor="w", font=header_font)
        label_web.grid(row=row, column=0, padx=10, pady=(50,10))
        # TODO: Port configuration. Can we easily restart the quart server while live, or require application restart?
        # TODO: Copy button for the overlay URL



        ######### TTS ##########
        row+=1
        column=0
        label_tts = ctk.CTkLabel(self.parent, text="TTS", anchor="w", font=header_font)
        label_tts.grid(row=row, column=0, padx=10, pady=(50,10))
        # Select a default for new members, later later later on toggle for use elevenlabs too (needs its own config section)


    def _update_bot_settings(self):
        self.chat_con_label.configure(text="Chat Connecting...", text_color="yellow")
        self.config.set(section="BOT", option="prefix", value=str(self.prefix_var.get()))
        self.config.set(section="BOT", option="speak_command", value=self.speak_cmd_var.get().strip())
        self.config.set(section="BOT", option="join_command", value=self.join_cmd_var.get().strip())
        self.config.set(section="TWITCH", option="channel", value=self.channel_var.get())
        self.config.write_updates()
        ui_settings_twitch_channel_update_event.trigger([True, self.twitch_utils, 5])
    

    def _update_bot_connection(self, status: bool):
        if status:
            self.chat_con_label.configure(text="Chat Connected", text_color="green")
        else:
            self.chat_con_label.configure(text="Chat Disconnected", text_color="red")
            self.parent.focus()

    def _update_twitch_connect(self, status: bool, twitchutils = None):
        if status:
            self.t_con_label.configure(text="Twitch Connected", text_color="green")
        else:
            self.t_con_label.configure(text="Twitch Disconnected", text_color="red")
            self.parent.focus()

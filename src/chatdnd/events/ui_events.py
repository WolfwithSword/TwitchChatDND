from helpers import Event

ui_settings_bot_settings_update_event = Event()
ui_settings_twitch_auth_update_event = Event()
ui_settings_twitch_channel_update_event = Event()
ui_on_startup_complete = Event()

ui_request_floating_notif = Event()
ui_remove_floating_notif = Event()
ui_fetch_update_check_event = Event()
ui_force_home_party_update = Event()

ui_refresh_user = Event()
ui_request_member_refresh = Event()
on_external_member_change = Event()

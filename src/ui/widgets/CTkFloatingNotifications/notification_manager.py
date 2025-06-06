from typing import List
from uuid import uuid4
from .notification_panel import NotificationPanel
from .notification_type import NotifyType

class NotificationManager:
    def __init__(self, master):
        self.master = master
        self.notifications: List[NotificationPanel] = []

    def show_notification(self, message, notify_type=NotifyType.INFO, duration=5000, bg_color="#dbdbdb", text_color="#262626", name:str = str(uuid4())):
        self.remove_by_name(name)
        NotificationPanel(self.master, self, message, notify_type=notify_type, duration=duration, bg_color=bg_color, text_color=text_color, name=name)

    def add_notification(self, notification):
        self.notifications.append(notification)
        self.update_notification_positions()

    def remove_notification(self, notification):
        if notification in self.notifications:
            self.notifications.remove(notification)
        self.update_notification_positions()

    def update_notification_positions(self):
        for index, notification in enumerate(self.notifications):
            y_offset = -20 - (index * 70)  # Adjust height as necessary
            notification.place(relx=1.0, rely=1.0, x=-20, y=y_offset, anchor="se")

    def remove_by_name(self, name:str, method="equals"):
        comparators = {
            "equals": lambda s, t: s == t,
            "starts_with": lambda s, t: s.startswith(t),
            "ends_with": lambda s, t: s.endswith(t),
            "contains": lambda s, t: t in s
        }
        for_removal: List[NotificationPanel] = []
        for notif in self.notifications:
            if comparators[method](notif.name, name):
                for_removal.append(notif)
                break
        while for_removal:
            for_removal.pop().remove_notification()

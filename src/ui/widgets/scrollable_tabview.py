from customtkinter import CTkScrollableFrame
from ui.widgets.custom_tabview import CTkTabview

class CTkScrollableTabView(CTkTabview):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._frames = {}

    def add(self, tab_name, scrollable: bool = True):
        if scrollable and tab_name in self._frames:
            raise ValueError(f"A tab named '{tab_name}' already exists")

        _frame = super().add(tab_name)
        if not scrollable:
            return _frame

        scrollframe = CTkScrollableFrame(self.tab(tab_name))

        scrollframe.pack(fill="both", expand=True)
        self._frames[tab_name] = scrollframe
        return scrollframe

    def get_scrollframe(self, tab_name):
        if tab_name not in self._frames:
            raise ValueError(f"No scrollframe tab found for '{tab_name}'")
        return self._frames[tab_name]

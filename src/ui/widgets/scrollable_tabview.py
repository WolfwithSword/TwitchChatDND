from customtkinter import CTkScrollableFrame
from ui.widgets.custom_tabview import CTkTabview


class CTkScrollableTabView(CTkTabview):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._frames = {}

    def add(self, name, scrollable: bool = True):
        if scrollable and name in self._frames:
            raise ValueError(f"A tab named '{name}' already exists")

        _frame = super().add(name)
        if not scrollable:
            return _frame

        scrollframe = CTkScrollableFrame(self.tab(name))

        scrollframe.pack(fill="both", expand=True)
        self._frames[name] = scrollframe
        return scrollframe

    def get_scrollframe(self, name):
        if name not in self._frames:
            raise ValueError(f"No scrollframe tab found for '{name}'")
        return self._frames[name]

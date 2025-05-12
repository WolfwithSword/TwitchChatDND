from enum import Enum, auto
import sys
from typing import Tuple
from customtkinter import CTkToplevel, CTkFrame, CTkButton


class ContextMenuTypes(Enum):
    NONE = auto()
    MEMBER_CARD = auto()
    QUEUE_ENTRY = auto()


class CTkContextMenu(CTkToplevel):
    """
    On-screen popup window class for customtkinter
    Author: Akascape
    Modified by: WolfwithSword
    """

    def __init__(self, master=None, corner_radius=12, border_width=1, **kwargs):
        super().__init__(takefocus=1)
        # super().__init__(master=master)
        self.master_window = master
        self.corner = corner_radius
        self.border = border_width
        self.hidden = True
        self.withdraw()
        self.update_idletasks()
        self.resizable(width=False, height=False)

        self.type = ContextMenuTypes.NONE

        # add transparency to suitable platforms
        if sys.platform.startswith("win"):
            self.after(100, lambda: self.overrideredirect(True))
            self.transparent_color = self._apply_appearance_mode(self._fg_color)
            self.attributes("-transparentcolor", self.transparent_color)
        elif sys.platform.startswith("darwin"):
            self.overrideredirect(True)
            self.transparent_color = "systemTransparent"
            self.attributes("-transparent", True)
        else:
            self.attributes("-type", "splash")
            self.transparent_color = "#000001"
            self.corner = 0
            self.withdraw()

        self.frame = CTkFrame(self, bg_color=self.transparent_color, corner_radius=self.corner, border_width=self.border, **kwargs)
        self.frame.pack(expand=True, fill="both", padx=0, pady=(4, 4))

        self.master.bind_all("<ButtonPress>", lambda event: self._withdraw_off(), add="+")
        self.master.bind_all("<Button-1>", lambda event: self._withdraw_off(), add="+")  # hide menu when clicked outside
        self.bind("<FocusOut>", lambda event: self._withdraw(), add="+")
        self.bind("<Button-1>", lambda event: self._withdraw())  # hide menu when clicked inside
        self.master.bind_all("<Key-Escape>", lambda event: self._withdraw(), add="+")
        self.master.bind("<Configure>", lambda event: self._withdraw())  # hide menu when master window is changed

        self.transient(self.master_window)
        self.update_idletasks()
        self.withdraw()

    def _withdraw(self):
        self.withdraw()
        self.hidden = True

    def _withdraw_off(self):
        if self.hidden:
            self.withdraw()
        self.hidden = True

    def popup(self, x=None, y=None):
        self._withdraw()
        self.x = x
        self.y = y
        self.deiconify()
        self.focus()
        self.update_idletasks()
        # self.geometry(f"+{self.x}+{self.y}")
        width = self.frame.winfo_reqwidth()
        height = self.frame.winfo_reqheight()
        self.geometry(f"{width-56}x{height+12}+{x}+{y}")  # TODO sizing is weird
        self.hidden = False

    def clear_contents(self):
        # self._withdraw()
        self.geometry(f"+{-5000}+{-5000}")
        for child in self.frame.winfo_children():
            child.destroy()

    def add_command(
        self,
        label: str,
        command: callable,
        padx: int | Tuple[int, int] = (4, 3),
        pady: int | Tuple[int, int] = (2, 2),
        fg_color: str = "transparent",
        hover_color: str = "#3C3F41",
        text_color: str = "#FFFFFF",
    ):
        new_btn = CTkButton(
            self.frame,
            text=label,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            anchor="w",
            height=24,
            border_width=0,
            border_spacing=2,
            corner_radius=8,
            command=command,
        )
        new_btn.pack(anchor="w", padx=padx, pady=pady, fill="x", expand=True)

    def add_separator(self, padx: int | Tuple[int, int] = (2, 2), pady: int | Tuple[int, int] = (2, 2), height: int = 2, color: str = "#333333"):
        separator = CTkFrame(self.frame, height=height, fg_color=color)
        separator.pack(anchor="w", padx=padx, pady=pady, fill="x", expand=True)

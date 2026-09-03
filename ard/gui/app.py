"""The ARD desktop window: five setup tabs plus the run / log tab."""

import logging
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox, ttk

from ..config import config
from .crud_tab import CrudTab
from .run_tab import RunTab
from .spec import SPECS


def enable_dpi_awareness() -> None:
    """Without this the window is rendered blurry on scaled Windows displays."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.log_dir / "ard.log", encoding="utf-8"),
        ],
    )


class ArdApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Automated Report Delivery")
        self._apply_style()
        self._size_window(1150, 780)
        self.minsize(880, 600)

        header = ttk.Frame(self, padding=(10, 8))
        header.pack(fill="x")
        ttk.Label(header, text="Automated Report Delivery",
                  font=("Segoe UI", 14, "bold")).pack(side="left")
        ttk.Label(header, text=f"{config.db_name} @ {config.db_host}:{config.db_port}",
                  foreground="#555").pack(side="right")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.run_tab = RunTab(notebook)
        # Editing a task or config changes the dropdowns on the run tab, so the
        # setup tabs refresh each other through on_change.
        self.crud_tabs = [CrudTab(notebook, spec, on_change=self._refresh_all)
                          for spec in SPECS]
        for tab, spec in zip(self.crud_tabs, SPECS):
            notebook.add(tab, text=spec.title)
        notebook.add(self.run_tab, text="6. Run and log")

    def _apply_style(self) -> None:
        """Tk keeps the default 20px row height even when the DPI-scaled font is
        taller, which clips the text - derive the row height from the font."""
        row_height = tkfont.nametofont("TkDefaultFont").metrics("linespace") + 8
        style = ttk.Style(self)
        style.configure("Treeview", rowheight=row_height)
        style.configure("Treeview.Heading", padding=(4, 4))

    def _size_window(self, width: int, height: int) -> None:
        """The size is given for a 96-dpi screen; Tk scales the fonts on a
        high-dpi one, so scale the window by the same factor."""
        factor = self.tk.call("tk", "scaling") / (96 / 72)
        width = min(int(width * factor), self.winfo_screenwidth() - 80)
        height = min(int(height * factor), self.winfo_screenheight() - 100)
        x = (self.winfo_screenwidth() - width) // 2
        y = max(0, (self.winfo_screenheight() - height) // 2 - 20)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _refresh_all(self) -> None:
        for tab in self.crud_tabs:
            tab.refresh()
        self.run_tab.refresh()


def main() -> int:
    enable_dpi_awareness()
    setup_logging()
    try:
        from .. import db
        with db.connect():
            pass
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Cannot reach the database",
            f"{exc}\n\nStart Postgres (docker compose up -d) and run\n"
            f"python -m ard --init-db --seed\nin {Path(__file__).parents[2]}",
        )
        return 1

    ArdApp().mainloop()
    return 0

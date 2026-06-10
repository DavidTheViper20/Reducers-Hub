from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import tkinter as tk
from tkinter import ttk


INVALID_FILENAME_PATTERN = re.compile(r'[<>:"/\\|?*]+')


@dataclass(frozen=True)
class ExportNameRequest:
    key: str
    label: str
    default_name: str


def build_export_path(
    output_dir: Path,
    default_stem: str,
    exported_at: datetime | None = None,
    file_name: str | None = None,
) -> Path:
    target_directory = Path(output_dir)
    target_directory.mkdir(parents=True, exist_ok=True)

    if file_name is not None:
        normalized_name = normalize_export_name(file_name, default_stem)
        return target_directory / f"{normalized_name}.dxf"

    timestamp = (exported_at or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return target_directory / f"{normalize_export_name(default_stem, default_stem)}-{timestamp}.dxf"


def normalize_export_name(file_name: str, default_stem: str) -> str:
    raw_name = Path(str(file_name).strip()).name
    if raw_name.lower().endswith(".dxf"):
        raw_name = raw_name[:-4]

    candidate = INVALID_FILENAME_PATTERN.sub("-", raw_name).strip().strip(".")
    return candidate or default_stem


def prompt_single_export_name(
    *,
    title: str,
    label: str,
    default_name: str,
) -> str | None:
    result = prompt_export_names(
        title=title,
        requests=[ExportNameRequest(key="file_name", label=label, default_name=default_name)],
    )
    if result is None:
        return None
    return result["file_name"]


def prompt_export_names(
    *,
    title: str,
    requests: list[ExportNameRequest],
) -> dict[str, str] | None:
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    dialog = _ExportNameDialog(root, title=title, requests=requests)
    root.wait_window(dialog.window)
    root.destroy()
    return dialog.result


class _ExportNameDialog:
    def __init__(self, master: tk.Tk, *, title: str, requests: list[ExportNameRequest]) -> None:
        self.result: dict[str, str] | None = None
        self.window = tk.Toplevel(master)
        self.window.title(title)
        self.window.resizable(False, False)
        self.window.transient(master)
        self.window.update_idletasks()
        self._center_window(master)
        self._raise_window()
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)

        content = ttk.Frame(self.window, padding=18)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(1, weight=1)

        self.entries: dict[str, ttk.Entry] = {}
        for index, request in enumerate(requests):
            ttk.Label(content, text=request.label).grid(row=index, column=0, sticky="w", padx=(0, 10), pady=(0, 10))
            entry = ttk.Entry(content, width=34)
            entry.grid(row=index, column=1, sticky="ew", pady=(0, 10))
            entry.insert(0, request.default_name)
            self.entries[request.key] = entry

        button_row = ttk.Frame(content)
        button_row.grid(row=len(requests), column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(button_row, text="Cancel", command=self._cancel).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(button_row, text="Export", command=self._submit).grid(row=0, column=1)

        first_entry = next(iter(self.entries.values()), None)
        if first_entry is not None:
            first_entry.focus_set()
            first_entry.selection_range(0, "end")
        self.window.bind("<Return>", lambda _event: self._submit())
        self.window.bind("<Escape>", lambda _event: self._cancel())
        self.window.update_idletasks()
        self._raise_window()

    def _submit(self) -> None:
        self.result = {key: entry.get().strip() for key, entry in self.entries.items()}
        self.window.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.window.destroy()

    def _center_window(self, master: tk.Tk) -> None:
        master.update_idletasks()
        width = max(self.window.winfo_reqwidth(), 360)
        height = max(self.window.winfo_reqheight(), 140)
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x_position = max((screen_width - width) // 2, 40)
        y_position = max((screen_height - height) // 2, 40)
        self.window.geometry(f"{width}x{height}+{x_position}+{y_position}")

    def _raise_window(self) -> None:
        self.window.lift()
        try:
            self.window.attributes("-topmost", True)
            self.window.after(160, lambda: self.window.attributes("-topmost", False))
        except tk.TclError:
            pass

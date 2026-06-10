from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from planetary_drive import DXF_UNITS_LABEL


REPO_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class DemoEntry:
    title: str
    description: str
    path: Path


def discover_demo_entries(repo_dir: Path = REPO_DIR) -> list[DemoEntry]:
    return [
        DemoEntry(
            title="Fixed-Ring Planetary Drive",
            description=(
                "Blue ring locked, red sun driving, green planets orbiting with the carrier output. "
                "This is the classic reduction layout."
            ),
            path=repo_dir / "demo_planetary_1.py",
        ),
        DemoEntry(
            title="Fixed-Carrier Ring Drive",
            description=(
                "Gray carrier held still while the blue ring drives the green planets in place and the red sun counter-rotates."
            ),
            path=repo_dir / "demo_planetary_2.py",
        ),
        DemoEntry(
            title="Fixed-Sun Ring Drive",
            description=(
                "Red sun locked while the blue ring drives the green planets around it, carrying the gray arm assembly as the output."
            ),
            path=repo_dir / "demo_planetary_3.py",
        ),
    ]


class PlanetaryHubPage(ttk.Frame):
    def __init__(
        self,
        master,
        on_back=None,
        title_callback=None,
        launch_python: str | None = None,
    ) -> None:
        super().__init__(master, padding=18)
        self.entries = discover_demo_entries(REPO_DIR)
        self.on_back = on_back
        self.title_callback = title_callback or self._set_window_title
        self.launch_python = launch_python or sys.executable
        self.status_var = tk.StringVar(value="Choose a demo and press Launch.")
        self.detail_title_var = tk.StringVar(value="No demo selected")
        self.detail_path_var = tk.StringVar(value="")
        self.detail_description_var = tk.StringVar(
            value="Planetary demos launch in their own windows and export DXFs from the starting pose."
        )

        self._build_ui()
        self._populate_entries()
        self.title_callback("Planetary")

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        ttk.Label(self, text="Planetary", font=("SF Pro Display", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text="Launch planetary reducer demos in the same outline-first house style. Use Back to return to the reducer families.",
        ).grid(row=1, column=0, sticky="w", pady=(4, 16))

        content = ttk.Frame(self)
        content.grid(row=2, column=0, sticky="nsew")
        content.columnconfigure(0, weight=2)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(content)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 18))

        self.listbox = tk.Listbox(
            list_frame,
            activestyle="none",
            font=("SF Pro Text", 13),
            exportselection=False,
            highlightthickness=1,
            relief="solid",
            selectbackground="#d7e6ff",
            selectforeground="#222222",
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._handle_selection)
        self.listbox.bind("<Double-Button-1>", self._launch_selected)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        detail_frame = ttk.Frame(content, padding=14)
        detail_frame.grid(row=0, column=1, sticky="nsew")
        detail_frame.columnconfigure(0, weight=1)

        ttk.Label(detail_frame, text="Details", font=("SF Pro Text", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            detail_frame,
            textvariable=self.detail_title_var,
            font=("SF Pro Text", 13, "bold"),
            wraplength=220,
        ).grid(row=1, column=0, sticky="w", pady=(12, 8))
        ttk.Label(detail_frame, textvariable=self.detail_path_var, wraplength=220, justify="left").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(detail_frame, textvariable=self.detail_description_var, wraplength=220, justify="left").grid(
            row=3, column=0, sticky="w", pady=(18, 0)
        )

        button_row = ttk.Frame(self)
        button_row.grid(row=3, column=0, sticky="ew", pady=(16, 10))
        button_row.columnconfigure(1, weight=1)

        ttk.Button(button_row, text="Back to Reducers Hub", command=self._handle_back).grid(row=0, column=0, sticky="w")
        ttk.Button(button_row, text="Launch Selected Demo", command=self._launch_selected).grid(row=0, column=2, sticky="e")

        ttk.Label(self, text=DXF_UNITS_LABEL).grid(row=4, column=0, sticky="w", pady=(0, 6))
        ttk.Label(self, textvariable=self.status_var).grid(row=5, column=0, sticky="w")

    def _populate_entries(self) -> None:
        for entry in self.entries:
            self.listbox.insert("end", entry.title)

        if self.entries:
            self.listbox.selection_set(0)
            self.listbox.event_generate("<<ListboxSelect>>")

    def _selected_entry(self) -> DemoEntry | None:
        selection = self.listbox.curselection()
        if not selection:
            return None
        return self.entries[selection[0]]

    def _handle_selection(self, _event=None) -> None:
        entry = self._selected_entry()
        if entry is None:
            self.detail_title_var.set("No demo selected")
            self.detail_path_var.set("")
            return

        self.detail_title_var.set(entry.title)
        self.detail_path_var.set(str(entry.path.relative_to(REPO_DIR)))
        self.detail_description_var.set(entry.description)
        self.status_var.set(f"Ready to launch {entry.title}.")
        self.title_callback(f"{entry.title} - Planetary")

    def _launch_selected(self, _event=None) -> None:
        entry = self._selected_entry()
        if entry is None:
            self.status_var.set("Choose a demo first.")
            return

        subprocess.Popen([self.launch_python, str(entry.path)], cwd=REPO_DIR)
        self.status_var.set(f"Launched {entry.title}.")

    def _handle_back(self) -> None:
        if self.on_back is not None:
            self.on_back()
            return

        root = self.winfo_toplevel()
        subprocess.Popen([self.launch_python, str(REPO_DIR.parent / "reducers_hub.py")], cwd=REPO_DIR.parent)
        root.destroy()

    def _set_window_title(self, title: str) -> None:
        try:
            self.winfo_toplevel().title(title)
        except Exception:
            pass


class DemoMenuApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Planetary")
        self.root.geometry("760x520")
        self.root.minsize(700, 460)
        self.root.configure(bg="#f4f1e8")

        self.page = PlanetaryHubPage(root)
        self.page.pack(fill="both", expand=True)


def build_embedded_page(master, on_back=None, title_callback=None, launch_python: str | None = None):
    return PlanetaryHubPage(
        master,
        on_back=on_back,
        title_callback=title_callback,
        launch_python=launch_python,
    )


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    if "aqua" in style.theme_names():
        style.theme_use("aqua")
    DemoMenuApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

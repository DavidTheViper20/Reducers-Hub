from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

REPO_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class MechanismEntry:
    filename: str
    title: str
    description: str


MECHANISMS = [
    MechanismEntry(
        "gerotor_pump.py",
        "Gerotor / Trochoidal Pump",
        "Inner N-lobe rotor enveloping N+1 outer circular teeth — the geometric cousin of the "
        "cycloidal drive. Speed ratio omega_in/omega_out = (N+1)/N. Sliders: lobe count, "
        "eccentricity, tooth-center radius, tooth radius.",
    ),
    MechanismEntry(
        "capstan_drive.py",
        "Capstan / Cable (Tendon) Drive",
        "A small input sheave and a larger output pulley linked by a wrapped cable. Shows both the "
        "kinematic reduction R_out/r_in and the separate Euler grip law T2/T1 = exp(mu*theta). "
        "Sliders: sheave radius, pulley radius, center distance, wraps, friction.",
    ),
    MechanismEntry(
        "non_circular_gears.py",
        "Non-Circular (Elliptical) Gears",
        "Twin identical ellipses rolling about their foci: a continuously varying ratio with a "
        "constant center distance C = 2a. Sliders: semi-major axis and ellipse eccentricity.",
    ),
    MechanismEntry(
        "geneva_drive.py",
        "Geneva Drive (Maltese Cross)",
        "Intermittent indexing drive: a continuously turning pin advances a slotted wheel by 360/n "
        "per revolution, then the locking disc holds it during dwell. Sliders: slot count and crank "
        "pin radius.",
    ),
    MechanismEntry(
        "friction_disc_cvt.py",
        "Friction Wheel-on-Disc CVT",
        "A continuously variable traction drive: a small wheel rolls on a spinning disc face. Ratio "
        "= contact_radius / wheel_radius, reversing through center (geared neutral). Sliders: disc "
        "radius, wheel radius, contact radius.",
    ),
    MechanismEntry(
        "antikythera_anomaly.py",
        "Antikythera Pin-and-Slot Lunar Anomaly",
        "Two gears on slightly offset centers, coupled by a pin riding in a slot, reproduce the "
        "Moon's varying speed. Constant input, varying output. Sliders: pin radius and center offset.",
    ),
]


class NovelReducersPage(ttk.Frame):
    def __init__(self, master, on_back=None, title_callback=None, launch_python: str | None = None) -> None:
        super().__init__(master, padding=18)
        self.entries = MECHANISMS
        self.on_back = on_back
        self.title_callback = title_callback or self._set_window_title
        self.launch_python = launch_python or sys.executable
        self.status_var = tk.StringVar(value="Choose a mechanism and press Launch.")
        self.detail_title_var = tk.StringVar(value="No mechanism selected")
        self.detail_description_var = tk.StringVar(value="Each mechanism opens its own animated window with sliders and DXF export.")

        self._build_ui()
        self._populate_entries()
        self.title_callback("Novel Reducers")

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        ttk.Label(self, text="Novel Reducers", font=("SF Pro Display", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text="Animated, customizable demos of unusual reducers and motion mechanisms. Each opens in its own window with sliders and DXF export.",
            wraplength=720,
            justify="left",
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
        ttk.Label(detail_frame, textvariable=self.detail_title_var, font=("SF Pro Text", 13, "bold"), wraplength=240).grid(
            row=1, column=0, sticky="w", pady=(12, 8)
        )
        ttk.Label(detail_frame, textvariable=self.detail_description_var, wraplength=240, justify="left").grid(
            row=2, column=0, sticky="w"
        )

        button_row = ttk.Frame(self)
        button_row.grid(row=3, column=0, sticky="ew", pady=(16, 10))
        button_row.columnconfigure(1, weight=1)

        ttk.Button(button_row, text="Back to Reducers Hub", command=self._handle_back).grid(row=0, column=0, sticky="w")
        ttk.Button(button_row, text="Launch Selected Mechanism", command=self._launch_selected).grid(row=0, column=2, sticky="e")

        ttk.Label(self, textvariable=self.status_var).grid(row=4, column=0, sticky="w")

    def _populate_entries(self) -> None:
        for entry in self.entries:
            self.listbox.insert("end", entry.title)
        if self.entries:
            self.listbox.selection_set(0)
            self.listbox.event_generate("<<ListboxSelect>>")

    def _selected_entry(self) -> MechanismEntry | None:
        selection = self.listbox.curselection()
        if not selection:
            return None
        return self.entries[selection[0]]

    def _handle_selection(self, _event=None) -> None:
        entry = self._selected_entry()
        if entry is None:
            self.detail_title_var.set("No mechanism selected")
            self.detail_description_var.set("")
            return
        self.detail_title_var.set(entry.title)
        self.detail_description_var.set(entry.description)
        self.status_var.set(f"Ready to launch {entry.title}.")
        self.title_callback(f"{entry.title} - Novel Reducers")

    def _launch_selected(self, _event=None) -> None:
        entry = self._selected_entry()
        if entry is None:
            self.status_var.set("Choose a mechanism first.")
            return
        subprocess.Popen([self.launch_python, str(REPO_DIR / entry.filename)], cwd=REPO_DIR)
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


def build_embedded_page(master, on_back=None, title_callback=None, launch_python: str | None = None):
    return NovelReducersPage(master, on_back=on_back, title_callback=title_callback, launch_python=launch_python)


class NovelReducersApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Novel Reducers")
        self.root.geometry("760x520")
        self.root.minsize(700, 460)
        self.root.configure(bg="#f4f1e8")
        self.page = NovelReducersPage(root)
        self.page.pack(fill="both", expand=True)


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    if "aqua" in style.theme_names():
        style.theme_use("aqua")
    NovelReducersApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

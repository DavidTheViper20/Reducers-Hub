from __future__ import annotations

import importlib.util
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk


ROOT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ReducerHubEntry:
    title: str
    description: str
    path: Path
    launch_target: Path | None
    status: str


def build_entries(root_dir: Path = ROOT_DIR) -> list[ReducerHubEntry]:
    cycloidal_path = root_dir / "Cycloidal Drive Demo Hub"
    cycloidal_demo_count = len(list(cycloidal_path.glob("demo*.py"))) + len(list(cycloidal_path.glob("Animation for how*.py")))
    planetary_path = root_dir / "Planetary"
    planetary_ready = (planetary_path / "main_menu.py").exists()
    harmonic_path = root_dir / "Harmonic"
    harmonic_ready = (harmonic_path / "main_menu.py").exists()
    logarithmic_path = root_dir / "Logarithmic Drive"
    logarithmic_ready = (logarithmic_path / "main_menu.py").exists()

    return [
        ReducerHubEntry(
            title="Cycloidal Drive Demo Hub",
            description=(
                f"Interactive hub for the cycloidal reducer demos in this collection. "
                f"Currently includes {cycloidal_demo_count} demos with DXF export tools."
            ),
            path=cycloidal_path,
            launch_target=cycloidal_path / "launch_cycloidal_drive.command",
            status="Ready",
        ),
        ReducerHubEntry(
            title="Planetary",
            description=(
                "Interactive hub for planetary reducer demos. "
                "Starts with a fixed-ring epicyclic stage in the same outline-first demo style."
                if planetary_ready
                else "Reserved for future planetary reducer scripts and launchers."
            ),
            path=planetary_path,
            launch_target=None,
            status="Ready" if planetary_ready else "Empty",
        ),
        ReducerHubEntry(
            title="Harmonic",
            description=(
                "Interactive hub for harmonic drive demos. Starts with a fixed-circular strain-wave reducer in the same outline-first demo style."
                if harmonic_ready
                else "Reserved for future harmonic drive scripts and launchers."
            ),
            path=harmonic_path,
            launch_target=None,
            status="Ready" if harmonic_ready else "Empty",
        ),
        ReducerHubEntry(
            title="Logarithmic Drive",
            description=(
                "Interactive hub for logarithmic-drive demos. Starts with the novel ball-bearing reducer built from the Promakina profile equations."
                if logarithmic_ready
                else "Reserved for future logarithmic drive scripts and launchers."
            ),
            path=logarithmic_path,
            launch_target=None,
            status="Ready" if logarithmic_ready else "Empty",
        ),
    ]


def load_family_page_builder(entry: ReducerHubEntry):
    module_path = entry.path / "main_menu.py"
    if not module_path.exists():
        return None

    module_name = f"reducers_hub_{_sanitize_module_name(entry.title)}_main_menu"
    module = sys.modules.get(module_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load reducer hub module from {module_path}")

        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(module_path.parent))
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            if sys.path and sys.path[0] == str(module_path.parent):
                sys.path.pop(0)

    builder = getattr(module, "build_embedded_page", None)
    if builder is None:
        raise RuntimeError(f"{module_path} does not define build_embedded_page(...).")
    return builder


class FamilySelectorPage(ttk.Frame):
    def __init__(self, master, entries: list[ReducerHubEntry], on_open) -> None:
        super().__init__(master, padding=18)
        self.entries = entries
        self.on_open = on_open
        self.status_var = tk.StringVar(value="Choose a reducer family.")
        self.detail_title_var = tk.StringVar(value="Choose a reducer family")
        self.detail_path_var = tk.StringVar(value="")
        self.detail_status_var = tk.StringVar(value="Status: Waiting for selection")
        self.detail_description_var = tk.StringVar(
            value="Pick a family from the list on the left to open its hub in this same window."
        )
        self._build_ui()
        self._populate_entries()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        ttk.Label(self, text="Reducers Hub", font=("SF Pro Display", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text="Choose a reducer family. Cycloidal, Planetary, Harmonic, and Logarithmic Drive each open their own embedded family hubs here.",
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
        self.listbox.bind("<Double-Button-1>", self._open_selected)

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
        ttk.Label(detail_frame, textvariable=self.detail_status_var, wraplength=220, justify="left").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(detail_frame, textvariable=self.detail_path_var, wraplength=220, justify="left").grid(
            row=3, column=0, sticky="w", pady=(10, 0)
        )
        ttk.Label(detail_frame, textvariable=self.detail_description_var, wraplength=220, justify="left").grid(
            row=4, column=0, sticky="w", pady=(18, 0)
        )

        button_row = ttk.Frame(self)
        button_row.grid(row=3, column=0, sticky="ew", pady=(16, 10))
        button_row.columnconfigure(0, weight=1)

        self.open_hub_button = ttk.Button(button_row, text="Open Selected Hub", command=self._open_selected, state="disabled")
        self.open_hub_button.grid(row=0, column=1, sticky="e")

        ttk.Label(self, textvariable=self.status_var).grid(row=4, column=0, sticky="w")

    def _populate_entries(self) -> None:
        for entry in self.entries:
            self.listbox.insert("end", entry.title)

    def _selected_entry(self) -> ReducerHubEntry | None:
        selection = self.listbox.curselection()
        if not selection:
            return None
        return self.entries[selection[0]]

    def _handle_selection(self, _event=None) -> None:
        entry = self._selected_entry()
        if entry is None:
            self.detail_title_var.set("Choose a reducer family")
            self.detail_path_var.set("")
            self.detail_status_var.set("Status: Waiting for selection")
            self.detail_description_var.set(
                "Pick a family from the list on the left to open its hub in this same window."
            )
            self.status_var.set("Choose a reducer family.")
            self.open_hub_button.configure(state="disabled")
            return

        self.detail_title_var.set(entry.title)
        self.detail_status_var.set(f"Status: {entry.status}")
        self.detail_path_var.set(str(entry.path.relative_to(ROOT_DIR)))
        self.detail_description_var.set(entry.description)
        self.status_var.set(f"Ready to open {entry.title}.")
        self.open_hub_button.configure(state="normal")

    def _open_selected(self, _event=None) -> None:
        entry = self._selected_entry()
        if entry is None:
            self.status_var.set("Choose a reducer family first.")
            return
        self.on_open(entry)


class PlaceholderHubPage(ttk.Frame):
    def __init__(self, master, entry: ReducerHubEntry, on_back) -> None:
        super().__init__(master, padding=18)
        self.entry = entry
        self.on_back = on_back
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text=self.entry.title, font=("SF Pro Display", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text=self.entry.description,
            wraplength=720,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 18))

        detail_text = (
            f"This hub is ready as a landing page for scripts placed in:\n"
            f"{self.entry.path}\n\n"
            f"Once you give me planetary, harmonic, or logarithmic reducer scripts, I can wire them into this page the same way the cycloidal family works now."
        )
        ttk.Label(self, text=detail_text, wraplength=720, justify="left").grid(row=2, column=0, sticky="w")

        ttk.Button(self, text="Back to Reducers Hub", command=self.on_back).grid(row=3, column=0, sticky="w", pady=(20, 0))


class ReducersHubApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.entries = build_entries()
        self.current_page = None

        self.root.title("Reducers Hub")
        self.root.geometry("760x520")
        self.root.minsize(700, 460)
        self.root.configure(bg="#f4f1e8")

        self.container = ttk.Frame(self.root)
        self.container.pack(fill="both", expand=True)

        self.show_family_selector()

    def show_family_selector(self) -> None:
        self.root.title("Reducers Hub")
        self._set_page(FamilySelectorPage(self.container, self.entries, self.open_entry))

    def open_entry(self, entry: ReducerHubEntry) -> None:
        page_builder = load_family_page_builder(entry)
        if page_builder is not None:
            self.root.title(entry.title)
            self._set_page(
                page_builder(
                    self.container,
                    on_back=self.show_family_selector,
                    title_callback=self.root.title,
                )
            )
            return

        self.root.title(f"{entry.title} - Reducers Hub")
        self._set_page(PlaceholderHubPage(self.container, entry, self.show_family_selector))

    def _set_page(self, page: ttk.Frame) -> None:
        if self.current_page is not None:
            self.current_page.destroy()
        self.current_page = page
        self.current_page.pack(fill="both", expand=True)


def _sanitize_module_name(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in value)


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    if "aqua" in style.theme_names():
        style.theme_use("aqua")
    ReducersHubApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

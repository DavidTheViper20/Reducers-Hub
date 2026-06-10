from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import ezdxf
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.widgets import Button, Slider

from cycloidal_drive import DXF_UNITS_LABEL, default_export_directory, reveal_in_finder

SHARED_UTILS_DIR = Path(__file__).resolve().parents[1]
if str(SHARED_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_UTILS_DIR))

from export_naming import build_export_path, prompt_single_export_name


REPO_DIR = Path(__file__).resolve().parent
CONTROL_BUTTON_COLOR = "lightgoldenrodyellow"
STATUS_TEXT_COLOR = "#444444"
STATUS_SUCCESS_COLOR = "#1b5e20"
STATUS_ERROR_COLOR = "#8b0000"
OPEN_FILES_LABEL = "Open\nFiles"

EXCLUDED_PYTHON_FILES = {
    "cycloidal_drive.py",
    "demo_hub.py",
    "demo1_new.py",
    "demo_output_equition.py",
    "main_menu.py",
}

DEMO_METADATA = {
    "Animation for how dual stage cycloidal gearbox works.py": (
        "Dual-Stage Gearbox Walkthrough",
        "Two cascaded cycloidal stages with output pins and both stage profiles visible together.",
    ),
    "Animation for how to combine two cycloidal drives together.py": (
        "Combined Dual Cycloidal Drives",
        "Pairs two cycloidal drives into one assembly so you can study how the red and blue stage families mesh together.",
    ),
    "demo_1.py": (
        "Single-Stage Base Drive",
        "Classic one-disc cycloidal drive with outer ring pins, inner pin ring, and the basic generated profile.",
    ),
    "demo_2.py": (
        "Dual-Disc Paired Profiles",
        "Two phased cycloidal discs with paired inner circles and mirrored red/blue profile traces.",
    ),
    "demo_3.py": (
        "Dual-Disc Alternate Phasing",
        "A two-disc variation that compares alternate inner-pin and profile phasing between the red and blue discs.",
    ),
    "demo_4.py": (
        "Main and Counter Profile Pair",
        "Shows a primary cycloidal branch and a counter-rotated companion branch driven from two inner-pin centers.",
    ),
    "demo_5.py": (
        "Minimal Two-Profile Study",
        "Profile-focused view with one drive center and a red/blue pair of generated cycloidal envelopes.",
    ),
    "demo_6.py": (
        "Four-Branch Envelope Study",
        "Profile-only study that traces four related hypocycloid branches around the same drive center.",
    ),
    "demo_7.py": (
        "Lambda-Controlled Single Profile",
        "Single-disc profile explorer with a layout-ratio control and visible inner ring hardware.",
    ),
    "demo_8.py": (
        "Lambda-Controlled Four-Branch Layout",
        "Four linked cycloidal branches with two colored inner-pin centers, useful for studying paired mirrored constructions.",
    ),
    "demo_9.py": (
        "Lambda-Controlled Two-Branch Layout",
        "Simplified branch study with one main profile family and one companion trace built from the same layout ratio.",
    ),
    "demo_10.py": (
        "Offset Output Pin Study",
        "Adds an alternate output-pin path to the base drive so you can compare the main disc with a secondary output branch.",
    ),
    "demo_11.py": (
        "Pin Contact Envelope Study",
        "Builds on the offset output-pin layout and also traces the pin-contact envelope path.",
    ),
    "demo_12.py": (
        "Basic Profile Generator",
        "Clean single-stage generator focused on the outer ring, drive pins, and the two visible cycloidal curves.",
    ),
    "demo_13.py": (
        "Dual Profile Generator",
        "Compares two generated profile families side by side for the same ring and eccentric drive geometry.",
    ),
    "demo_14.py": (
        "Cycloidal Ring Explorer",
        "Centered ring-and-profile explorer matching the reference screenshot, with the cleanest single-stage presentation in the repo.",
    ),
    "demo_15.py": (
        "Output Pin Configuration Explorer",
        "Single-stage output-pin layout with radio options for configuration, pin visibility, and motion mode.",
    ),
    "demo_16.py": (
        "Compact Two-Curve Envelope Study",
        "Compact profile study focused on the red and blue envelope pair around the central drive.",
    ),
    "demo_17.py": (
        "Single Stage with Inner Pin Ring",
        "Single-stage drive that keeps both the outer profile pair and the internal green pin ring visible together.",
    ),
    "demo_18.py": (
        "Tooth Family Sweep Study",
        "Repeats many related profile branches around one drive so you can see how tooth families stack into a dense pattern.",
    ),
    "demo_19.py": (
        "Reduction Pattern Sweep",
        "Another repeated-branch study, this time emphasizing how the reduction choice changes the red/blue pattern families.",
    ),
    "demo_20.py": (
        "Rolling Circle Construction",
        "Geometric construction view centered on the rolling and generating circles rather than the full pin ring.",
    ),
    "demo_21.py": (
        "Four-Profile Reduction View",
        "Shows four simultaneous hypocycloid branches with a visible inner pin for reduction-ratio shape study.",
    ),
    "demo_22.py": (
        "Dual-Stage Reduction Explorer",
        "Two-stage reduction demo with separate primary and secondary pin counts and pin-circle diameters.",
    ),
    "demo_ThreeStageA.py": (
        "Three-Stage Cycloidal Drive",
        "Three synchronized cycloidal stages with separate inner-circle packs and three profile families.",
    ),
    "demo_UI_ver1.py": (
        "UI Explorer - Single, Dual, Triple",
        "Interactive control panel for switching between single-, dual-, and triple-cycloid layouts with pin and motion modes.",
    ),
    "demo_UI_ver1.1.py": (
        "UI Explorer - Curves and Modes",
        "Expanded UI explorer with curve selection, motion selection, and single-, dual-, or triple-stage views.",
    ),
    "cycloidal_roller_drive_free_cage.py": (
        "Cycloidal Drive with Intermediate Rollers and Free Cage",
        "Animation with cam gear, crown gear, intermediate rollers, and free cage — with DXF export.",
    ),
    "wolfrom_cycloidal_planetary.py": (
        "Wolfrom Cycloidal Planetary Generator",
        "Two-stage Wolfrom-style differential planetary drive with live ratio controls, lock-ratio mode, and dual DXF export.",
    ),
}

SLIDER_LABEL_ALIASES = {
    "fm": "Animation Frames",
    "Rm": "Rotor Radius",
    "n": "Lobe Count",
    "Rd": "Center Circle Radius",
    "rd": "Drive Pin Radius",
    "e": "Eccentricity",
    "N": "Number of Pins",
    "d": "Ring Pin Diameter",
    "D": "Pin Circle Diameter",
    "N1": "Primary Pin Count",
    "N2": "Secondary Pin Count",
    "D1": "Primary Pin Circle Diameter",
    "D2": "Secondary Pin Circle Diameter",
    "la": "Layout Ratio",
}


@dataclass(frozen=True)
class DemoEntry:
    identifier: str
    title: str
    description: str
    path: Path


def discover_demo_entries(repo_dir: Path = REPO_DIR) -> list[DemoEntry]:
    entries = []

    for path in sorted(repo_dir.glob("*.py"), key=_demo_sort_key):
        if path.name in EXCLUDED_PYTHON_FILES:
            continue

        if not (path.name.startswith("demo") or path.name.startswith("Animation for how") or path.name in DEMO_METADATA):
            continue

        title, description = DEMO_METADATA.get(path.name, (_friendly_demo_title(path.stem), "Cycloidal drive demo."))

        entries.append(
            DemoEntry(
                identifier=path.stem,
                title=title,
                description=description,
                path=path,
            )
        )

    return entries


def friendly_slider_label(label: str) -> str:
    return SLIDER_LABEL_ALIASES.get(label, label)


def export_plot_axes_to_dxf(
    axis,
    file_stem: str,
    output_dir: Path | None = None,
    exported_at: datetime | None = None,
    file_name: str | None = None,
) -> Path:
    target_directory = Path(output_dir) if output_dir is not None else default_export_directory(REPO_DIR)
    target_directory.mkdir(parents=True, exist_ok=True)
    output_path = build_export_path(
        target_directory,
        default_stem=_sanitize_file_stem(file_stem),
        exported_at=exported_at,
        file_name=file_name,
    )

    document = ezdxf.new(setup=True)
    document.units = ezdxf.units.MM
    modelspace = document.modelspace()
    if "plot_lines" not in document.layers:
        document.layers.add("plot_lines", color=1)

    exported_count = 0
    for line in axis.lines:
        points = _line_to_points(line)
        if len(points) < 2:
            continue

        close_shape = _points_are_closed(points)
        modelspace.add_lwpolyline(points, close=close_shape, dxfattribs={"layer": "plot_lines"})
        exported_count += 1

    if exported_count == 0:
        raise RuntimeError("No drawable linework found on the selected plot axes.")

    document.saveas(output_path)
    return output_path


def run_demo_entry(entry: DemoEntry) -> None:
    install_matplotlib_compatibility_patches()

    module_name = f"cycloidal_runtime_{_sanitize_module_name(entry.path.stem)}"
    original_show = plt.show
    decorated = {"done": False}
    module_holder = {"module": None}

    def wrapped_show(*args, **kwargs):
        if not decorated["done"] and module_holder["module"] is not None:
            decorate_demo_window(module_holder["module"], entry)
            decorated["done"] = True
        return original_show(*args, **kwargs)

    plt.show = wrapped_show
    sys.path.insert(0, str(entry.path.parent))
    original_argv = sys.argv[:]
    sys.argv = [str(entry.path)]

    try:
        spec = importlib.util.spec_from_file_location(module_name, entry.path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load demo script: {entry.path}")

        module = importlib.util.module_from_spec(spec)
        module_holder["module"] = module
        spec.loader.exec_module(module)
    finally:
        plt.show = original_show
        sys.argv = original_argv
        if sys.path and sys.path[0] == str(entry.path.parent):
            sys.path.pop(0)


def decorate_demo_window(module, entry: DemoEntry) -> None:
    figure = _resolve_figure(module)

    if getattr(module, "_has_custom_layout", False):
        _set_window_title(figure, entry.title)
        return

    primary_axis = select_primary_axes(figure)
    _normalize_primary_axes(primary_axis)
    _apply_slider_label_aliases(module)
    control_layout = _normalize_control_layout(module)
    _set_window_title(figure, entry.title)

    if _module_already_has_export(module):
        return

    state = {"last_export_path": None}
    status_text = figure.text(
        0.02,
        control_layout["status_y"],
        "DXF exports will be saved to ~/Desktop/Cycloidal Drive Exports.",
        fontsize=9,
        color=STATUS_TEXT_COLOR,
    )
    figure.text(0.02, control_layout["units_y"], DXF_UNITS_LABEL, fontsize=9, color=STATUS_TEXT_COLOR)

    open_location_axis = figure.add_axes(control_layout["open_button"])
    open_location_button = Button(open_location_axis, OPEN_FILES_LABEL, color=CONTROL_BUTTON_COLOR, hovercolor="0.975")
    open_location_button.label.set_fontsize(9)
    export_axis = figure.add_axes(control_layout["export_button"])
    export_button = Button(export_axis, "Export DXF", color=CONTROL_BUTTON_COLOR, hovercolor="0.975")
    export_button.label.set_fontsize(10)

    def handle_export(_event) -> None:
        try:
            file_name = prompt_single_export_name(
                title=f"Export {entry.title} DXF",
                label="DXF file name",
                default_name=entry.path.stem,
            )
            if file_name is None:
                status_text.set_text("DXF export canceled.")
                status_text.set_color(STATUS_TEXT_COLOR)
                figure.canvas.draw_idle()
                return
            prepare_demo_for_export(module)
            output_path = export_plot_axes_to_dxf(primary_axis, entry.path.stem, file_name=file_name)
            state["last_export_path"] = output_path
            status_text.set_text(f"DXF exported from the starting pose to {str(output_path.parent).replace(str(Path.home()), '~', 1)}")
            status_text.set_color(STATUS_SUCCESS_COLOR)
            print(f"DXF exported to {output_path}")
        except Exception as error:
            status_text.set_text(f"DXF export failed: {error}")
            status_text.set_color(STATUS_ERROR_COLOR)
            print(f"DXF export failed: {error}")

        figure.canvas.draw_idle()

    def handle_open_file_location(_event) -> None:
        if state["last_export_path"] is None:
            export_directory = default_export_directory(REPO_DIR)
            export_directory.mkdir(parents=True, exist_ok=True)
            subprocess.run(["open", str(export_directory)], check=False)
            status_text.set_text(f"Opened export folder: {str(export_directory).replace(str(Path.home()), '~', 1)}")
            status_text.set_color(STATUS_SUCCESS_COLOR)
            figure.canvas.draw_idle()
            return

        try:
            reveal_in_finder(state["last_export_path"])
            status_text.set_text(f"Revealed in Finder: {state['last_export_path'].name}")
            status_text.set_color(STATUS_SUCCESS_COLOR)
        except Exception as error:
            status_text.set_text(f"Finder reveal failed: {error}")
            status_text.set_color(STATUS_ERROR_COLOR)

        figure.canvas.draw_idle()

    open_location_button.on_clicked(handle_open_file_location)
    export_button.on_clicked(handle_export)
    _store_wrapped_controls(
        module,
        figure,
        {
            "entry": entry,
            "state": state,
            "status_text": status_text,
            "open_location_axis": open_location_axis,
            "open_location_button": open_location_button,
            "export_axis": export_axis,
            "export_button": export_button,
            "handle_open_file_location": handle_open_file_location,
            "handle_export": handle_export,
        },
    )


def prepare_demo_for_export(module) -> None:
    if hasattr(module, "render_scene"):
        module.render_scene(0.0)
    elif hasattr(module, "animate"):
        module.animate(0)

    figure = _resolve_figure(module)
    if hasattr(figure.canvas, "draw_idle"):
        figure.canvas.draw_idle()


def select_primary_axes(figure):
    candidates = [axis for axis in figure.axes if axis.get_visible()]
    if not candidates:
        raise RuntimeError("No visible axes were found in the demo figure.")

    large_candidates = [axis for axis in candidates if _is_plot_sized_axes(axis)]
    if large_candidates:
        return max(large_candidates, key=_axes_score)

    return max(candidates, key=_axes_score)


def install_matplotlib_compatibility_patches() -> None:
    if getattr(Line2D.set_data, "_cycloidal_hub_patched", False):
        return

    original_set_data = Line2D.set_data

    def patched_set_data(self, *args):
        if len(args) == 2:
            x_values, y_values = args
            return original_set_data(self, _coerce_plot_sequence(x_values), _coerce_plot_sequence(y_values))

        return original_set_data(self, *args)

    patched_set_data._cycloidal_hub_patched = True
    Line2D.set_data = patched_set_data


def _resolve_figure(module):
    if hasattr(module, "figure"):
        return module.figure
    if hasattr(module, "fig"):
        return module.fig

    figures = [plt.figure(number) for number in plt.get_fignums()]
    if not figures:
        raise RuntimeError("The demo did not create a matplotlib figure.")

    return figures[-1]


def _apply_slider_label_aliases(module) -> None:
    for value in vars(module).values():
        if isinstance(value, Slider):
            value.label.set_text(friendly_slider_label(value.label.get_text()))
            value.label.set_fontsize(10)
            value.valtext.set_fontsize(10)


def _normalize_control_layout(module) -> dict[str, list[float] | float]:
    if getattr(module, "_has_custom_layout", False):
        return {}

    _space_slider_stack(module)
    buttons = [value for value in vars(module).values() if isinstance(value, Button)]
    reset_button = next((button for button in buttons if button.label.get_text().strip().lower() == "reset"), None)

    if len(buttons) <= 1:
        if reset_button is not None:
            reset_button.ax.set_position([0.20, 0.01, 0.10, 0.04])
        return {
            "open_button": [0.31, 0.01, 0.12, 0.04],
            "export_button": [0.44, 0.01, 0.14, 0.04],
            "units_y": 0.046,
            "status_y": 0.018,
        }

    if reset_button is not None:
        reset_button.ax.set_position([0.20, 0.01, 0.10, 0.04])

    return {
        "open_button": [0.31, 0.01, 0.12, 0.04],
        "export_button": [0.44, 0.01, 0.14, 0.04],
        "units_y": 0.046,
        "status_y": 0.018,
    }


def _space_slider_stack(module) -> None:
    sliders = [value for value in vars(module).values() if isinstance(value, Slider)]
    if not sliders:
        return

    sliders = sorted(sliders, key=lambda slider: slider.ax.get_position().y0)
    bottom_anchor = 0.098
    top_limit = 0.268
    slider_height = min(slider.ax.get_position().height for slider in sliders)
    slider_height = min(slider_height, 0.016)

    if len(sliders) == 1:
        step = 0.0
    else:
        available_span = max(top_limit - bottom_anchor - slider_height, 0.10)
        step = available_span / (len(sliders) - 1)
        step = max(step, 0.024)

    current_top = bottom_anchor + step * max(len(sliders) - 1, 0) + slider_height
    if current_top > top_limit:
        overflow = current_top - top_limit
        bottom_anchor = max(0.08, bottom_anchor - overflow)

    for index, slider in enumerate(sliders):
        position = slider.ax.get_position()
        slider.ax.set_position([position.x0, bottom_anchor + step * index, position.width, slider_height])


def _normalize_primary_axes(primary_axis) -> None:
    position = primary_axis.get_position()
    target_bottom = 0.41
    target_top = 0.93
    height = min(position.height, target_top - target_bottom)
    height = max(height, 0.42)
    height = min(height, target_top - target_bottom)
    y0 = max(position.y0, target_bottom)
    if y0 + height > target_top:
        y0 = target_top - height
    primary_axis.set_position([position.x0, y0, position.width, height])


def _store_wrapped_controls(module, figure, controls: dict) -> None:
    setattr(module, "_cycloidal_hub_controls", controls)
    setattr(figure, "_cycloidal_hub_controls", controls)
    for control in controls.values():
        if isinstance(control, Button):
            setattr(control.ax, "_button", control)


def _module_already_has_export(module) -> bool:
    return hasattr(module, "export_link_text") or hasattr(module, "handle_export")


def _set_window_title(figure, title: str) -> None:
    try:
        figure.canvas.manager.set_window_title(f"{title} - Cycloidal Drive Hub")
    except Exception:
        pass


def _axes_score(axis) -> tuple[float, float]:
    line_point_count = sum(len(_line_to_points(line)) for line in axis.lines if line.get_visible())
    position = axis.get_position()
    area = position.width * position.height
    return (line_point_count, area)


def _is_plot_sized_axes(axis) -> bool:
    position = axis.get_position()
    return position.width >= 0.28 and position.height >= 0.28


def _line_to_points(line: Line2D) -> list[tuple[float, float]]:
    if not line.get_visible():
        return []

    x_values = np.asarray(line.get_xdata(), dtype=float)
    y_values = np.asarray(line.get_ydata(), dtype=float)
    if x_values.size == 0 or y_values.size == 0:
        return []

    finite_mask = np.isfinite(x_values) & np.isfinite(y_values)
    x_values = x_values[finite_mask]
    y_values = y_values[finite_mask]
    if x_values.size < 2 or y_values.size < 2:
        return []

    return [(float(x_value), float(y_value)) for x_value, y_value in zip(x_values, y_values)]


def _points_are_closed(points: list[tuple[float, float]]) -> bool:
    if len(points) < 3:
        return False

    first_x, first_y = points[0]
    last_x, last_y = points[-1]
    return abs(first_x - last_x) < 1e-9 and abs(first_y - last_y) < 1e-9


def _coerce_plot_sequence(values):
    if np.isscalar(values):
        return [values]
    return values


def _friendly_demo_title(stem: str) -> str:
    if stem.startswith("demo_"):
        return stem.replace("_", " ").title()
    if stem.startswith("demo"):
        suffix = stem[len("demo") :]
        if suffix and suffix[0].isdigit():
            return f"Demo {suffix}"
        return stem.replace("_", " ").title()
    return stem.replace("_", " ").title()


def _sanitize_file_stem(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return sanitized or "cycloidal-demo"


def _sanitize_module_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value)


def _demo_sort_key(path: Path) -> tuple[int, str]:
    match = re.match(r"demo_(\d+)$", path.stem)
    if match:
        return (0, f"{int(match.group(1)):04d}")
    return (1, path.stem.lower())


def _find_entry_by_name(repo_dir: Path, requested_name: str) -> DemoEntry:
    entries = discover_demo_entries(repo_dir)
    for entry in entries:
        if entry.path.name == requested_name or entry.identifier == requested_name:
            return entry
    raise RuntimeError(f"Demo not found: {requested_name}")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shared runner for Cycloidal Drive demos.")
    parser.add_argument("--demo", help="Demo filename or identifier to launch.")
    parser.add_argument("--list", action="store_true", help="Print the available demos.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.list:
        for entry in discover_demo_entries(REPO_DIR):
            print(f"{entry.path.name}\t{entry.title}")
        return 0

    if not args.demo:
        parser.error("--demo is required unless --list is used.")

    entry = _find_entry_by_name(REPO_DIR, args.demo)
    run_demo_entry(entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

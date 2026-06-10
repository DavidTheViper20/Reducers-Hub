from __future__ import annotations

import itertools
import subprocess
from pathlib import Path
import sys

import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Button, Slider

from harmonic_drive import (
    DXF_UNITS_LABEL,
    HarmonicParameters,
    build_scene_geometry,
    default_export_directory,
    export_scene_to_dxf,
    reveal_in_finder,
)

SHARED_UTILS_DIR = Path(__file__).resolve().parents[1]
if str(SHARED_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_UTILS_DIR))

from export_naming import prompt_single_export_name


INTERVAL_MS = 40
AXIS_COLOR = "lightgoldenrodyellow"
STATUS_TEXT_COLOR = "#444444"
STATUS_SUCCESS_COLOR = "#1b5e20"
STATUS_ERROR_COLOR = "#8b0000"
DEFAULT_ANIMATION_FRAMES = 72
DEFAULT_SPEED_SCALE = 0.6
DEFAULT_WAVE_GENERATOR_COMPRESSION = 0.9


def coupled_tooth_counts(changed_key: str, flex_teeth: int, circular_teeth: int) -> tuple[int, int]:
    if changed_key == "flex_teeth":
        flex_teeth = max(20, int(flex_teeth))
        return flex_teeth, flex_teeth + 2
    circular_teeth = max(22, int(circular_teeth))
    return circular_teeth - 2, circular_teeth


SLIDER_SPECS = (
    ("animation_frames", "Animation Frames", 12, 140, DEFAULT_ANIMATION_FRAMES, 1),
    ("module", "Module", 0.6, 2.4, 1.2, 0.05),
    ("flex_teeth", "Flex Spline Teeth", 20, 80, 40, 1),
    ("circular_teeth", "Circular Spline Teeth", 22, 82, 42, 1),
    ("tooth_depth", "Tooth Depth", 0.4, 2.2, 1.0, 0.05),
    ("bore_radius", "Bore Radius", 2.0, 14.0, 6.0, 0.1),
    ("pressure_angle_degrees", "Pressure Angle", 10.0, 35.0, 24.0, 0.5),
)


def animation_step_radians(animation_frames: int) -> float:
    safe_frames = max(int(animation_frames), 1)
    legacy_default_step = (2.0 * np.pi) / DEFAULT_ANIMATION_FRAMES
    return legacy_default_step * DEFAULT_SPEED_SCALE * (safe_frames / DEFAULT_ANIMATION_FRAMES)


def aligned_pose_angle_for_parameter_change(_current_angle: float) -> float:
    return 0.0


def run_demo() -> None:
    figure, axis = plt.subplots(figsize=(8.9, 8.6))
    plt.subplots_adjust(left=0.10, bottom=0.44, right=0.965, top=0.91)

    axis.set_aspect("equal")
    axis.set_xlim(-48, 48)
    axis.set_ylim(-48, 48)

    try:
        figure.canvas.manager.set_window_title("Harmonic Drive Animator")
    except Exception:
        pass

    circular_artist, = axis.plot([], [], color="#2a55e5", linewidth=2.2, zorder=3)
    circular_body_artist, = axis.plot([], [], color="#2a55e5", linewidth=1.6, zorder=2)
    flex_artist, = axis.plot([], [], color="forestgreen", linewidth=2.0, zorder=5)
    wave_artist, = axis.plot([], [], color="red", linewidth=2.0, zorder=4)
    flex_inner_artist, = axis.plot([], [], color="forestgreen", linewidth=1.5, zorder=6)
    wave_inner_artist, = axis.plot([], [], color="red", linewidth=1.5, zorder=4)
    bore_artist, = axis.plot([], [], color="black", linewidth=1.4, zorder=7)

    status_text = figure.text(
        0.02,
        0.018,
        "DXF exports will be saved to ~/Desktop/Harmonic Drive Exports.",
        fontsize=9,
        color=STATUS_TEXT_COLOR,
    )
    figure.text(0.02, 0.046, DXF_UNITS_LABEL, fontsize=9, color=STATUS_TEXT_COLOR)

    slider_bottom = 0.095
    slider_top = 0.355
    slider_height = 0.020
    slider_step = (slider_top - slider_bottom) / max(len(SLIDER_SPECS) - 1, 1)

    sliders: dict[str, Slider] = {}
    slider_axes = []
    for index, (parameter_key, label, minimum, maximum, default, step) in enumerate(SLIDER_SPECS):
        y_position = slider_top - index * slider_step
        slider_axis = plt.axes([0.30, y_position, 0.47, slider_height], facecolor=AXIS_COLOR)
        slider = Slider(
            slider_axis,
            label,
            minimum,
            maximum,
            valinit=default,
            valstep=step,
            dragging=True,
        )
        slider.label.set_fontsize(10)
        slider.valtext.set_fontsize(10)
        sliders[parameter_key] = slider
        slider_axes.append(slider_axis)

    open_files_button_axis = plt.axes([0.81, 0.114, 0.15, 0.048])
    open_files_button = Button(open_files_button_axis, "Open\nFiles", color=AXIS_COLOR, hovercolor="0.975")
    open_files_button.label.set_fontsize(9)

    reset_button_axis = plt.axes([0.81, 0.061, 0.15, 0.048])
    reset_button = Button(reset_button_axis, "Reset", color=AXIS_COLOR, hovercolor="0.975")
    reset_button.label.set_fontsize(10)

    export_button_axis = plt.axes([0.81, 0.008, 0.15, 0.048])
    export_button = Button(export_button_axis, "Export DXF", color=AXIS_COLOR, hovercolor="0.975")
    export_button.label.set_fontsize(10)

    animation_state = {
        "input_angle": 0.0,
        "last_export_path": None,
        "slider_drag_active": False,
        "syncing_teeth": False,
    }

    def current_parameters() -> HarmonicParameters:
        flex_teeth = int(sliders["flex_teeth"].val)
        circular_teeth = int(sliders["circular_teeth"].val)
        return HarmonicParameters(
            animation_frames=int(sliders["animation_frames"].val),
            module=float(sliders["module"].val),
            flex_teeth=flex_teeth,
            circular_teeth=circular_teeth,
            tooth_depth=float(sliders["tooth_depth"].val),
            wave_generator_thickness=DEFAULT_WAVE_GENERATOR_COMPRESSION,
            bore_radius=float(sliders["bore_radius"].val),
            pressure_angle_degrees=float(sliders["pressure_angle_degrees"].val),
        )

    def format_path_for_display(path: Path) -> str:
        try:
            return str(path).replace(str(Path.home()), "~", 1)
        except Exception:
            return str(path)

    def update_axis_limits(parameters: HarmonicParameters) -> None:
        limit = parameters.circular_body_radius + parameters.tooth_depth * 1.8
        axis.set_xlim(-limit, limit)
        axis.set_ylim(-limit, limit)

    def render_scene(input_angle: float) -> None:
        parameters = current_parameters()
        geometry = build_scene_geometry(parameters, input_angle=input_angle)
        animation_state["input_angle"] = input_angle
        update_axis_limits(parameters)

        circular_artist.set_data(geometry.circular_spline_outline[:, 0], geometry.circular_spline_outline[:, 1])
        circular_body_artist.set_data(geometry.circular_body_outline[:, 0], geometry.circular_body_outline[:, 1])
        flex_artist.set_data(geometry.flex_spline_outline[:, 0], geometry.flex_spline_outline[:, 1])
        flex_inner_artist.set_data(geometry.flex_inner_outline[:, 0], geometry.flex_inner_outline[:, 1])
        wave_artist.set_data(geometry.wave_generator_outline[:, 0], geometry.wave_generator_outline[:, 1])
        wave_inner_artist.set_data(geometry.wave_generator_inner_outline[:, 0], geometry.wave_generator_inner_outline[:, 1])
        bore_artist.set_data(geometry.bore_circle[:, 0], geometry.bore_circle[:, 1])

        axis.set_title(
            f"{geometry.mode_label}\nTooth Difference: {parameters.tooth_difference}   Reduction Ratio: {geometry.reduction_ratio:.2f}:1   "
            f"Pressure Angle: {parameters.pressure_angle_degrees:.1f} deg   Derived Wave: {parameters.wave_amplitude:.2f}",
            fontsize=11,
            pad=10,
        )

    def handle_slider_change(_value) -> None:
        aligned_angle = aligned_pose_angle_for_parameter_change(animation_state["input_angle"])
        animation_state["input_angle"] = aligned_angle
        render_scene(aligned_angle)
        figure.canvas.draw_idle()

    def handle_flex_teeth_change(value) -> None:
        if animation_state["syncing_teeth"]:
            return
        animation_state["syncing_teeth"] = True
        try:
            flex_teeth, circular_teeth = coupled_tooth_counts("flex_teeth", int(round(value)), int(round(sliders["circular_teeth"].val)))
            if int(round(sliders["circular_teeth"].val)) != circular_teeth:
                sliders["circular_teeth"].set_val(circular_teeth)
            if int(round(sliders["flex_teeth"].val)) != flex_teeth:
                sliders["flex_teeth"].set_val(flex_teeth)
        finally:
            animation_state["syncing_teeth"] = False
        handle_slider_change(value)

    def handle_circular_teeth_change(value) -> None:
        if animation_state["syncing_teeth"]:
            return
        animation_state["syncing_teeth"] = True
        try:
            flex_teeth, circular_teeth = coupled_tooth_counts("circular_teeth", int(round(sliders["flex_teeth"].val)), int(round(value)))
            if int(round(sliders["flex_teeth"].val)) != flex_teeth:
                sliders["flex_teeth"].set_val(flex_teeth)
            if int(round(sliders["circular_teeth"].val)) != circular_teeth:
                sliders["circular_teeth"].set_val(circular_teeth)
        finally:
            animation_state["syncing_teeth"] = False
        handle_slider_change(value)

    def handle_reset(_event) -> None:
        animation_state["input_angle"] = 0.0
        for slider in sliders.values():
            slider.reset()
        flex_teeth, circular_teeth = coupled_tooth_counts("circular_teeth", int(sliders["flex_teeth"].val), int(sliders["circular_teeth"].val))
        sliders["flex_teeth"].set_val(flex_teeth)
        sliders["circular_teeth"].set_val(circular_teeth)
        render_scene(0.0)
        figure.canvas.draw_idle()

    def handle_export(_event) -> None:
        parameters = current_parameters()
        try:
            file_name = prompt_single_export_name(
                title="Export Harmonic DXF",
                label="DXF file name",
                default_name="harmonic-drive",
            )
            if file_name is None:
                status_text.set_text("DXF export canceled.")
                status_text.set_color(STATUS_TEXT_COLOR)
                figure.canvas.draw_idle()
                return
            output_path = export_scene_to_dxf(parameters, input_angle=0.0, file_name=file_name)
            animation_state["last_export_path"] = output_path
            status_text.set_text(f"DXF exported from the starting pose to {format_path_for_display(output_path.parent)}")
            status_text.set_color(STATUS_SUCCESS_COLOR)
        except Exception as error:
            status_text.set_text(f"DXF export failed: {error}")
            status_text.set_color(STATUS_ERROR_COLOR)
        figure.canvas.draw_idle()

    def handle_open_files(_event) -> None:
        if animation_state["last_export_path"] is None:
            export_directory = default_export_directory(Path(__file__).resolve().parent)
            export_directory.mkdir(parents=True, exist_ok=True)
            subprocess.run(["open", str(export_directory)], check=False)
            status_text.set_text(f"Opened export folder: {format_path_for_display(export_directory)}")
            status_text.set_color(STATUS_SUCCESS_COLOR)
            figure.canvas.draw_idle()
            return

        try:
            reveal_in_finder(animation_state["last_export_path"])
            status_text.set_text(f"Revealed in Finder: {animation_state['last_export_path'].name}")
            status_text.set_color(STATUS_SUCCESS_COLOR)
        except Exception as error:
            status_text.set_text(f"Finder reveal failed: {error}")
            status_text.set_color(STATUS_ERROR_COLOR)
        figure.canvas.draw_idle()

    def handle_press(event) -> None:
        if event.inaxes in slider_axes and not animation_state["slider_drag_active"]:
            animation_state["slider_drag_active"] = True
            if ani.event_source is not None:
                ani.event_source.stop()

    def handle_release(_event) -> None:
        if animation_state["slider_drag_active"]:
            animation_state["slider_drag_active"] = False
            if ani.event_source is not None:
                ani.event_source.start()

    def animate(_frame: int) -> None:
        if animation_state["slider_drag_active"]:
            return
        parameters = current_parameters()
        next_angle = animation_state["input_angle"] + animation_step_radians(parameters.animation_frames)
        render_scene(next_angle)

    for key, slider in sliders.items():
        if key == "flex_teeth":
            slider.on_changed(handle_flex_teeth_change)
        elif key == "circular_teeth":
            slider.on_changed(handle_circular_teeth_change)
        else:
            slider.on_changed(handle_slider_change)

    open_files_button.on_clicked(handle_open_files)
    reset_button.on_clicked(handle_reset)
    export_button.on_clicked(handle_export)
    render_scene(0.0)

    figure.canvas.mpl_connect("button_press_event", handle_press)
    figure.canvas.mpl_connect("button_release_event", handle_release)
    ani = animation.FuncAnimation(figure, animate, frames=itertools.count(), interval=INTERVAL_MS, cache_frame_data=False)
    plt.show()

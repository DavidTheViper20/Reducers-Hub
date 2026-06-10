from __future__ import annotations

import itertools
import subprocess
from pathlib import Path
import sys

import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.widgets import Button, Slider

from logarithmic_drive import (
    DXF_UNITS_LABEL,
    LogarithmicParameters,
    build_scene_geometry,
    default_export_directory,
    export_scene_to_dxf,
    export_split_scene_to_dxf,
    reveal_in_finder,
)

SHARED_UTILS_DIR = Path(__file__).resolve().parents[1]
if str(SHARED_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_UTILS_DIR))

from export_naming import ExportNameRequest, prompt_export_names


INTERVAL_MS = 40
MAX_BALLS = 40
AXIS_COLOR = "lightgoldenrodyellow"
STATUS_TEXT_COLOR = "#444444"
STATUS_SUCCESS_COLOR = "#1b5e20"
STATUS_ERROR_COLOR = "#8b0000"
DEFAULT_ANIMATION_FRAMES = 72
DEFAULT_SPEED_SCALE = 0.6

SLIDER_SPECS = (
    ("animation_frames", "Animation Frames", 12, 140, DEFAULT_ANIMATION_FRAMES, 1),
    ("cusp_count", "Cusp Count", 6, 40, 26, 2),
    ("input_track_size", "Input Track Size", 10.0, 40.0, 25.0, 0.5),
    ("input_track_short_width", "Input Track Short Width", 15.0, 80.0, 50.0, 1.0),
    ("ball_radius", "Ball Radius", 0.8, 6.0, 2.5, 0.1),
    ("clearance", "Running Clearance", 0.0, 1.5, 0.0, 0.05),
)


def animation_step_radians(animation_frames: int) -> float:
    safe_frames = max(int(animation_frames), 1)
    legacy_default_step = (2.0 * np.pi) / DEFAULT_ANIMATION_FRAMES
    return legacy_default_step * DEFAULT_SPEED_SCALE * (safe_frames / DEFAULT_ANIMATION_FRAMES)


def run_demo() -> None:
    figure, axis = plt.subplots(figsize=(8.9, 8.6))
    plt.subplots_adjust(left=0.10, bottom=0.43, right=0.965, top=0.91)

    axis.set_aspect("equal")
    axis.set_xlim(-72, 72)
    axis.set_ylim(-72, 72)

    try:
        figure.canvas.manager.set_window_title("Novel Logarithmic Drive Animator")
    except Exception:
        pass

    ellipse_artist, = axis.plot([], [], color="#ff3b30", linewidth=2.2, zorder=6)
    hypocycloid_artist, = axis.plot([], [], color="#7aa5ff", linewidth=1.2, linestyle="--", alpha=0.45, zorder=2)
    output_trochoid_artist, = axis.plot([], [], color="#ff9f0a", linewidth=2.3, zorder=5)
    slot_artists = [axis.plot([], [], color="dimgray", linewidth=1.15, zorder=2)[0] for _ in range(MAX_BALLS)]
    ball_artists = [axis.plot([], [], color="forestgreen", linewidth=1.8, zorder=4)[0] for _ in range(MAX_BALLS)]
    ball_center_markers = [axis.plot([], [], "o", color="white", markeredgecolor="#8c8c8c", markersize=4, zorder=7)[0] for _ in range(MAX_BALLS)]
    legend_handles = [
        Line2D([0], [0], color="#ff3b30", lw=2.2),
        Line2D([0], [0], color="dimgray", lw=1.2),
        Line2D([0], [0], color="#ff9f0a", lw=2.3),
        Line2D([0], [0], color="forestgreen", lw=1.8),
    ]
    axis.legend(
        legend_handles,
        ["Input Track", "Modulator Slots", "Output Track", "Balls"],
        loc="upper left",
        fontsize=8.5,
        frameon=False,
    )

    status_text = figure.text(
        0.02,
        0.018,
        "DXF exports will be saved to ~/Desktop/Logarithmic Drive Exports.",
        fontsize=9,
        color=STATUS_TEXT_COLOR,
    )
    figure.text(0.02, 0.046, DXF_UNITS_LABEL, fontsize=9, color=STATUS_TEXT_COLOR)

    slider_bottom = 0.115
    slider_top = 0.355
    slider_height = 0.022
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

    output_button_axis = plt.axes([0.81, 0.220, 0.15, 0.048])
    output_button = Button(output_button_axis, "Output Shape\nOn", color=AXIS_COLOR, hovercolor="0.975")
    output_button.label.set_fontsize(9)

    open_files_button_axis = plt.axes([0.81, 0.167, 0.15, 0.048])
    open_files_button = Button(open_files_button_axis, "Open\nFiles", color=AXIS_COLOR, hovercolor="0.975")
    open_files_button.label.set_fontsize(9)

    reset_button_axis = plt.axes([0.81, 0.114, 0.15, 0.048])
    reset_button = Button(reset_button_axis, "Reset", color=AXIS_COLOR, hovercolor="0.975")
    reset_button.label.set_fontsize(10)

    export_button_axis = plt.axes([0.81, 0.061, 0.15, 0.048])
    export_button = Button(export_button_axis, "Export DXF", color=AXIS_COLOR, hovercolor="0.975")
    export_button.label.set_fontsize(10)

    animation_state = {
        "input_angle": 0.0,
        "last_export_paths": None,
        "show_output_trochoid": True,
        "slider_drag_active": False,
    }

    def current_parameters() -> LogarithmicParameters:
        return LogarithmicParameters(
            animation_frames=int(sliders["animation_frames"].val),
            cusp_count=int(sliders["cusp_count"].val),
            minor_axis_radius=float(sliders["input_track_size"].val),
            ball_radius=float(sliders["ball_radius"].val),
            clearance=float(sliders["clearance"].val),
            show_every_other=False,
            input_track_short_width=float(sliders["input_track_short_width"].val),
        )

    def format_path_for_display(path: Path) -> str:
        try:
            return str(path).replace(str(Path.home()), "~", 1)
        except Exception:
            return str(path)

    def update_toggle_label() -> None:
        output_button.label.set_text(f"Output Shape\n{'On' if animation_state['show_output_trochoid'] else 'Off'}")

    def update_axis_limits(parameters: LogarithmicParameters) -> None:
        limit = parameters.major_axis_radius + parameters.hole_radius + parameters.ball_radius + 8.0
        axis.set_xlim(-limit, limit)
        axis.set_ylim(-limit, limit)

    def render_scene(input_angle: float) -> None:
        parameters = current_parameters()
        geometry = build_scene_geometry(parameters, input_angle=input_angle)
        animation_state["input_angle"] = input_angle
        update_axis_limits(parameters)

        ellipse_artist.set_data(geometry.ellipse_outline[:, 0], geometry.ellipse_outline[:, 1])
        hypocycloid_artist.set_data(geometry.hypocycloid_outline[:, 0], geometry.hypocycloid_outline[:, 1])
        if animation_state["show_output_trochoid"]:
            output_trochoid_artist.set_data(
                geometry.output_trochoid_outline[:, 0],
                geometry.output_trochoid_outline[:, 1],
            )
        else:
            output_trochoid_artist.set_data([], [])

        for index in range(MAX_BALLS):
            if index < len(geometry.slot_outlines):
                slot_artists[index].set_data(geometry.slot_outlines[index][:, 0], geometry.slot_outlines[index][:, 1])
                ball_artists[index].set_data(geometry.ball_circles[index][:, 0], geometry.ball_circles[index][:, 1])
                center_x, center_y = geometry.ball_centers[index]
                ball_center_markers[index].set_data([center_x], [center_y])
            else:
                slot_artists[index].set_data([], [])
                ball_artists[index].set_data([], [])
                ball_center_markers[index].set_data([], [])

        axis.set_title(
            f"{geometry.mode_label}\nBalls: {len(geometry.ball_centers)}   Reduction Ratio: {geometry.reduction_ratio:.2f}:1",
            fontsize=11,
            pad=10,
        )

    def handle_slider_change(_value) -> None:
        render_scene(animation_state["input_angle"])
        figure.canvas.draw_idle()

    def handle_reset(_event) -> None:
        animation_state["input_angle"] = 0.0
        animation_state["show_output_trochoid"] = True
        update_toggle_label()
        for slider in sliders.values():
            slider.reset()
        render_scene(0.0)
        figure.canvas.draw_idle()

    def handle_toggle_output(_event) -> None:
        animation_state["show_output_trochoid"] = not animation_state["show_output_trochoid"]
        update_toggle_label()
        render_scene(animation_state["input_angle"])
        figure.canvas.draw_idle()

    def handle_export(_event) -> None:
        parameters = current_parameters()
        try:
            names = prompt_export_names(
                title="Export Logarithmic DXFs",
                requests=[
                    ExportNameRequest(
                        key="input_file_name",
                        label="Input and balls file name",
                        default_name="logarithmic-input-and-balls",
                    ),
                    ExportNameRequest(
                        key="output_file_name",
                        label="Output shape file name",
                        default_name="logarithmic-output-shape",
                    ),
                ],
            )
            if names is None:
                status_text.set_text("DXF export canceled.")
                status_text.set_color(STATUS_TEXT_COLOR)
                figure.canvas.draw_idle()
                return
            input_path, output_path = export_split_scene_to_dxf(
                parameters,
                input_angle=0.0,
                input_file_name=names["input_file_name"],
                output_file_name=names["output_file_name"],
            )
            animation_state["last_export_paths"] = [input_path, output_path]
            status_text.set_text(f"DXF pair exported from the starting pose to {format_path_for_display(output_path.parent)}")
            status_text.set_color(STATUS_SUCCESS_COLOR)
        except Exception as error:
            status_text.set_text(f"DXF export failed: {error}")
            status_text.set_color(STATUS_ERROR_COLOR)
        figure.canvas.draw_idle()

    def handle_open_files(_event) -> None:
        if animation_state["last_export_paths"] is None:
            export_directory = default_export_directory(Path(__file__).resolve().parent)
            export_directory.mkdir(parents=True, exist_ok=True)
            subprocess.run(["open", str(export_directory)], check=False)
            status_text.set_text(f"Opened export folder: {format_path_for_display(export_directory)}")
            status_text.set_color(STATUS_SUCCESS_COLOR)
            figure.canvas.draw_idle()
            return

        try:
            export_directory = animation_state["last_export_paths"][0].parent
            subprocess.run(["open", str(export_directory)], check=False)
            status_text.set_text(f"Opened export folder: {format_path_for_display(export_directory)}")
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

    for slider in sliders.values():
        slider.on_changed(handle_slider_change)

    output_button.on_clicked(handle_toggle_output)
    open_files_button.on_clicked(handle_open_files)
    reset_button.on_clicked(handle_reset)
    export_button.on_clicked(handle_export)
    update_toggle_label()
    render_scene(0.0)

    figure.canvas.mpl_connect("button_press_event", handle_press)
    figure.canvas.mpl_connect("button_release_event", handle_release)
    ani = animation.FuncAnimation(figure, animate, frames=itertools.count(), interval=INTERVAL_MS, cache_frame_data=False)
    plt.show()

from __future__ import annotations

import itertools
import subprocess
from pathlib import Path
import sys

import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Button, Slider

from planetary_drive import (
    DEFAULT_MODE_KEY,
    DXF_UNITS_LABEL,
    PLANETARY_MODE_SPECS,
    PlanetaryParameters,
    build_scene_geometry,
    default_export_directory,
    export_scene_to_dxf,
    reveal_in_finder,
)

SHARED_UTILS_DIR = Path(__file__).resolve().parents[1]
if str(SHARED_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_UTILS_DIR))

from export_naming import prompt_single_export_name


INTERVAL_MS = 33
MAX_PLANETS = 6
AXIS_COLOR = "lightgoldenrodyellow"
STATUS_TEXT_COLOR = "#444444"
STATUS_SUCCESS_COLOR = "#1b5e20"
STATUS_ERROR_COLOR = "#8b0000"
DEFAULT_ANIMATION_FRAMES = 72
DEFAULT_SPEED_SCALE = 0.6

SLIDER_SPECS = (
    ("animation_frames", "Animation Frames", 12, 140, DEFAULT_ANIMATION_FRAMES, 1),
    ("module", "Module", 0.6, 4.0, 2.0, 0.1),
    ("sun_teeth", "Sun Gear Teeth", 8, 36, 18, 1),
    ("planet_teeth", "Planet Gear Teeth", 6, 24, 12, 1),
    ("planet_count", "Number of Planets", 2, 6, 3, 1),
    ("tooth_depth", "Tooth Depth", 0.8, 5.0, 2.6, 0.1),
    ("sun_bore_radius", "Sun Bore Radius", 1.0, 12.0, 5.0, 0.1),
    ("planet_bore_radius", "Planet Bore Radius", 1.0, 10.0, 3.0, 0.1),
    ("pressure_angle_degrees", "Pressure Angle", 10.0, 35.0, 20.0, 0.5),
)


def animation_step_radians(animation_frames: int) -> float:
    safe_frames = max(int(animation_frames), 1)
    legacy_default_step = (2.0 * np.pi) / DEFAULT_ANIMATION_FRAMES
    return legacy_default_step * DEFAULT_SPEED_SCALE * (safe_frames / DEFAULT_ANIMATION_FRAMES)


def aligned_pose_angle_for_parameter_change(_current_angle: float) -> float:
    return 0.0


def run_demo(mode_key: str = DEFAULT_MODE_KEY) -> None:
    mode_spec = PLANETARY_MODE_SPECS[mode_key]
    angle_direction = -1.0 if "ring_input" in mode_key else 1.0
    figure, axis = plt.subplots(figsize=(8.9, 8.6))
    plt.subplots_adjust(left=0.10, bottom=0.45, right=0.965, top=0.91)

    axis.set_aspect("equal")
    axis.set_xlim(-68, 68)
    axis.set_ylim(-68, 68)

    try:
        figure.canvas.manager.set_window_title(mode_spec.title)
    except Exception:
        pass

    ring_outer_artist, = axis.plot([], [], color="#2a55e5", linewidth=2.2)
    ring_inner_artist, = axis.plot([], [], color="#2a55e5", linewidth=2.2)
    sun_artist, = axis.plot([], [], color="red", linewidth=2.0)
    sun_bore_artist, = axis.plot([], [], color="black", linewidth=1.5)
    carrier_hub_artist, = axis.plot([], [], color="dimgray", linewidth=1.6)
    carrier_arm_artists = [axis.plot([], [], color="dimgray", linewidth=1.4)[0] for _ in range(MAX_PLANETS)]
    planet_outline_artists = [axis.plot([], [], color="forestgreen", linewidth=2.0)[0] for _ in range(MAX_PLANETS)]
    planet_bore_artists = [axis.plot([], [], color="black", linewidth=1.3)[0] for _ in range(MAX_PLANETS)]

    status_text = figure.text(
        0.02,
        0.018,
        "DXF exports will be saved to ~/Desktop/Planetary Gear Exports.",
        fontsize=9,
        color=STATUS_TEXT_COLOR,
    )
    figure.text(
        0.02,
        0.046,
        DXF_UNITS_LABEL,
        fontsize=9,
        color=STATUS_TEXT_COLOR,
    )

    slider_bottom = 0.102
    slider_top = 0.362
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

    sun_bore_button_axis = plt.axes([0.81, 0.206, 0.15, 0.044])
    sun_bore_button = Button(sun_bore_button_axis, "Sun Bore\nOn", color=AXIS_COLOR, hovercolor="0.975")
    sun_bore_button.label.set_fontsize(9)

    planet_bore_button_axis = plt.axes([0.81, 0.154, 0.15, 0.044])
    planet_bore_button = Button(planet_bore_button_axis, "Planet Bores\nOn", color=AXIS_COLOR, hovercolor="0.975")
    planet_bore_button.label.set_fontsize(9)

    open_files_button_axis = plt.axes([0.81, 0.102, 0.15, 0.044])
    open_files_button = Button(open_files_button_axis, "Open\nFiles", color=AXIS_COLOR, hovercolor="0.975")
    open_files_button.label.set_fontsize(9)

    reset_button_axis = plt.axes([0.81, 0.050, 0.15, 0.044])
    reset_button = Button(reset_button_axis, "Reset", color=AXIS_COLOR, hovercolor="0.975")
    reset_button.label.set_fontsize(10)

    export_button_axis = plt.axes([0.81, 0.004, 0.15, 0.040])
    export_button = Button(export_button_axis, "Export DXF", color=AXIS_COLOR, hovercolor="0.975")
    export_button.label.set_fontsize(10)

    animation_state = {
        "input_angle": 0.0,
        "last_export_path": None,
        "show_sun_bore": True,
        "show_planet_bores": True,
        "slider_drag_active": False,
    }

    def current_parameters() -> PlanetaryParameters:
        return PlanetaryParameters(
            animation_frames=int(sliders["animation_frames"].val),
            module=float(sliders["module"].val),
            sun_teeth=int(sliders["sun_teeth"].val),
            planet_teeth=int(sliders["planet_teeth"].val),
            planet_count=int(sliders["planet_count"].val),
            tooth_depth=float(sliders["tooth_depth"].val),
            sun_bore_radius=float(sliders["sun_bore_radius"].val),
            planet_bore_radius=float(sliders["planet_bore_radius"].val),
            pressure_angle_degrees=float(sliders["pressure_angle_degrees"].val),
        )

    def format_path_for_display(path: Path) -> str:
        try:
            return str(path).replace(str(Path.home()), "~", 1)
        except Exception:
            return str(path)

    def update_toggle_labels() -> None:
        sun_bore_button.label.set_text(f"Sun Bore\n{'On' if animation_state['show_sun_bore'] else 'Off'}")
        planet_bore_button.label.set_text(f"Planet Bores\n{'On' if animation_state['show_planet_bores'] else 'Off'}")

    def update_axis_limits(parameters: PlanetaryParameters) -> None:
        limit = parameters.ring_outer_radius * 1.12
        axis.set_xlim(-limit, limit)
        axis.set_ylim(-limit, limit)

    def render_scene(input_angle: float) -> None:
        parameters = current_parameters()
        geometry = build_scene_geometry(parameters, input_angle=input_angle, mode_key=mode_key)
        animation_state["input_angle"] = input_angle
        update_axis_limits(parameters)

        ring_outer_artist.set_data(geometry.ring_outer_circle[:, 0], geometry.ring_outer_circle[:, 1])
        ring_inner_artist.set_data(geometry.ring_inner_outline[:, 0], geometry.ring_inner_outline[:, 1])
        sun_artist.set_data(geometry.sun_outline[:, 0], geometry.sun_outline[:, 1])
        carrier_hub_artist.set_data(geometry.carrier_hub_circle[:, 0], geometry.carrier_hub_circle[:, 1])

        if animation_state["show_sun_bore"]:
            sun_bore_artist.set_data(geometry.sun_bore_circle[:, 0], geometry.sun_bore_circle[:, 1])
        else:
            sun_bore_artist.set_data([], [])

        for index in range(MAX_PLANETS):
            if index < len(geometry.planet_outlines):
                planet_outline_artists[index].set_data(
                    geometry.planet_outlines[index][:, 0],
                    geometry.planet_outlines[index][:, 1],
                )
                carrier_arm_artists[index].set_data(
                    geometry.carrier_arm_segments[index][:, 0],
                    geometry.carrier_arm_segments[index][:, 1],
                )
                if animation_state["show_planet_bores"]:
                    planet_bore_artists[index].set_data(
                        geometry.planet_bore_circles[index][:, 0],
                        geometry.planet_bore_circles[index][:, 1],
                    )
                else:
                    planet_bore_artists[index].set_data([], [])
            else:
                planet_outline_artists[index].set_data([], [])
                carrier_arm_artists[index].set_data([], [])
                planet_bore_artists[index].set_data([], [])

        requested_count = int(round(parameters.planet_count))
        detail_suffix = ""
        if geometry.effective_planet_count != requested_count:
            detail_suffix = f"   Showing {geometry.effective_planet_count} planets"

        axis.set_title(
            f"{geometry.mode_label}\nRing Gear Teeth: {geometry.ring_teeth}   "
            f"{geometry.ratio_label}: {geometry.ratio_value:.2f}:1{detail_suffix}",
            fontsize=11,
            pad=10,
        )

    def handle_slider_change(_value) -> None:
        aligned_angle = aligned_pose_angle_for_parameter_change(animation_state["input_angle"])
        animation_state["input_angle"] = aligned_angle
        render_scene(aligned_angle)
        figure.canvas.draw_idle()

    def handle_reset(_event) -> None:
        animation_state["input_angle"] = 0.0
        animation_state["show_sun_bore"] = True
        animation_state["show_planet_bores"] = True
        update_toggle_labels()
        for slider in sliders.values():
            slider.reset()
        render_scene(0.0)
        figure.canvas.draw_idle()

    def handle_toggle_sun_bore(_event) -> None:
        animation_state["show_sun_bore"] = not animation_state["show_sun_bore"]
        update_toggle_labels()
        render_scene(animation_state["input_angle"])
        figure.canvas.draw_idle()

    def handle_toggle_planet_bores(_event) -> None:
        animation_state["show_planet_bores"] = not animation_state["show_planet_bores"]
        update_toggle_labels()
        render_scene(animation_state["input_angle"])
        figure.canvas.draw_idle()

    def handle_export(_event) -> None:
        parameters = current_parameters()
        try:
            file_name = prompt_single_export_name(
                title="Export Planetary DXF",
                label="DXF file name",
                default_name=mode_spec.export_stem,
            )
            if file_name is None:
                status_text.set_text("DXF export canceled.")
                status_text.set_color(STATUS_TEXT_COLOR)
                figure.canvas.draw_idle()
                return
            output_path = export_scene_to_dxf(
                parameters,
                input_angle=0.0,
                mode_key=mode_key,
                include_sun_bore=animation_state["show_sun_bore"],
                include_planet_bores=animation_state["show_planet_bores"],
                file_name=file_name,
            )
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
        next_angle = animation_state["input_angle"] + angle_direction * animation_step_radians(parameters.animation_frames)
        render_scene(next_angle)

    for slider in sliders.values():
        slider.on_changed(handle_slider_change)

    sun_bore_button.on_clicked(handle_toggle_sun_bore)
    planet_bore_button.on_clicked(handle_toggle_planet_bores)
    open_files_button.on_clicked(handle_open_files)
    reset_button.on_clicked(handle_reset)
    export_button.on_clicked(handle_export)
    update_toggle_labels()
    render_scene(0.0)

    figure.canvas.mpl_connect("button_press_event", handle_press)
    figure.canvas.mpl_connect("button_release_event", handle_release)
    ani = animation.FuncAnimation(figure, animate, frames=itertools.count(), interval=INTERVAL_MS, cache_frame_data=False)
    plt.show()

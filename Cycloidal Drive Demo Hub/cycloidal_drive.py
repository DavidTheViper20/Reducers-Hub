from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import subprocess
import sys

import numpy as np

try:
    import ezdxf
except ImportError:  # pragma: no cover - handled at runtime by the launcher/UI.
    ezdxf = None

SHARED_UTILS_DIR = Path(__file__).resolve().parents[1]
if str(SHARED_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_UTILS_DIR))

from export_naming import build_export_path


DEFAULT_SAMPLE_COUNT = 2000
DEFAULT_EXPORT_FOLDER_NAME = "Cycloidal Drive Exports"
DXF_UNITS_LABEL = "DXF units: millimeters (mm)."


@dataclass(frozen=True)
class DriveParameters:
    animation_frames: int
    center_circle_radius: float
    drive_pin_radius: float
    eccentricity: float
    pin_count: int
    outer_pin_diameter: float
    pin_circle_diameter: float

    @property
    def outer_pin_radius(self) -> float:
        return self.outer_pin_diameter / 2.0

    @property
    def pitch_circle_radius(self) -> float:
        return self.pin_circle_diameter / 2.0


@dataclass(frozen=True)
class SceneGeometry:
    outer_pin_centers: list[tuple[float, float]]
    outer_pin_radius: float
    drive_pin_centers: list[tuple[float, float]]
    drive_pin_radius: float
    inner_circle_radius: float
    hypocycloid_a: np.ndarray
    hypocycloid_b: np.ndarray


def sample_circle_points(
    center: tuple[float, float],
    radius: float,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * np.pi, sample_count)
    x = center[0] + radius * np.sin(theta)
    y = center[1] + radius * np.cos(theta)
    return np.column_stack((x, y))


def build_scene_geometry(
    parameters: DriveParameters,
    phi: float,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
) -> SceneGeometry:
    pin_count = max(2, int(round(parameters.pin_count)))
    theta = np.linspace(0.0, 2.0 * np.pi, sample_count)
    outer_pin_centers = _build_outer_pin_centers(parameters, pin_count, phi)
    drive_pin_centers = _build_drive_pin_centers(parameters, pin_count, phi)

    return SceneGeometry(
        outer_pin_centers=outer_pin_centers,
        outer_pin_radius=parameters.outer_pin_radius,
        drive_pin_centers=drive_pin_centers,
        drive_pin_radius=parameters.drive_pin_radius,
        inner_circle_radius=parameters.center_circle_radius,
        hypocycloid_a=_build_hypocycloid_a(parameters, pin_count, phi, theta),
        hypocycloid_b=_build_hypocycloid_b(parameters, pin_count, theta),
    )


def default_export_directory(fallback_root: Path | None = None) -> Path:
    desktop_directory = Path.home() / "Desktop"
    if desktop_directory.exists():
        return desktop_directory / DEFAULT_EXPORT_FOLDER_NAME

    root = fallback_root or Path.cwd()
    return root / "exports"


def export_scene_to_dxf(
    parameters: DriveParameters,
    phi: float,
    output_dir: Path | None = None,
    exported_at: datetime | None = None,
    file_name: str | None = None,
) -> Path:
    if ezdxf is None:
        raise RuntimeError("DXF export requires the ezdxf package.")

    geometry = build_scene_geometry(parameters, phi)
    target_directory = Path(output_dir) if output_dir is not None else default_export_directory(Path(__file__).resolve().parent)
    target_directory.mkdir(parents=True, exist_ok=True)

    output_path = build_export_path(
        target_directory,
        default_stem="cycloidal-drive",
        exported_at=exported_at,
        file_name=file_name,
    )

    document = ezdxf.new(setup=True)
    document.units = ezdxf.units.MM
    modelspace = document.modelspace()

    _add_layers(document)

    for center in geometry.outer_pin_centers:
        modelspace.add_circle(center, geometry.outer_pin_radius, dxfattribs={"layer": "outer_pins"})

    for center in geometry.drive_pin_centers:
        modelspace.add_circle(center, geometry.drive_pin_radius, dxfattribs={"layer": "drive_pins"})

    modelspace.add_circle((0.0, 0.0), geometry.inner_circle_radius, dxfattribs={"layer": "center_circle"})
    modelspace.add_lwpolyline(geometry.hypocycloid_a.tolist(), close=True, dxfattribs={"layer": "cycloid_a"})
    modelspace.add_lwpolyline(geometry.hypocycloid_b.tolist(), close=True, dxfattribs={"layer": "cycloid_b"})
    document.saveas(output_path)
    return output_path


def reveal_in_finder(path: Path, runner=subprocess.run) -> None:
    runner(["open", "-R", str(path)], check=True)


def _add_layers(document) -> None:
    layers = (
        ("outer_pins", 3),
        ("drive_pins", 7),
        ("center_circle", 1),
        ("cycloid_a", 1),
        ("cycloid_b", 5),
    )

    for name, color in layers:
        if name not in document.layers:
            document.layers.add(name, color=color)


def _build_outer_pin_centers(parameters: DriveParameters, pin_count: int, phi: float) -> list[tuple[float, float]]:
    centers = []
    rotation = -phi / (pin_count + 1)

    for index in range(pin_count):
        angle = 2.0 * np.pi * index / pin_count
        x_base = parameters.pitch_circle_radius * np.cos(angle) + parameters.eccentricity * np.cos(phi)
        y_base = parameters.pitch_circle_radius * np.sin(angle) + parameters.eccentricity * np.sin(phi)
        centers.append(_rotate_point(x_base, y_base, rotation))

    return centers


def _build_drive_pin_centers(parameters: DriveParameters, pin_count: int, phi: float) -> list[tuple[float, float]]:
    centers = []
    rotation = -phi / (pin_count + 1)

    for index in range(pin_count):
        angle = 2.0 * np.pi * index / pin_count
        x_base = parameters.pitch_circle_radius * np.cos(angle)
        y_base = parameters.pitch_circle_radius * np.sin(angle)
        centers.append(_rotate_point(x_base, y_base, rotation))

    return centers


def _build_hypocycloid_a(
    parameters: DriveParameters,
    pin_count: int,
    phi: float,
    theta: np.ndarray,
) -> np.ndarray:
    pitch_circle_radius = parameters.pitch_circle_radius
    outer_pin_radius = parameters.outer_pin_radius
    rolling_circle_radius = pitch_circle_radius / pin_count
    generating_circle_radius = (pin_count - 1) * rolling_circle_radius
    ratio = (generating_circle_radius + rolling_circle_radius) / rolling_circle_radius

    x_base = (generating_circle_radius + rolling_circle_radius) * np.cos(theta) - parameters.eccentricity * np.cos(ratio * theta)
    y_base = (generating_circle_radius + rolling_circle_radius) * np.sin(theta) - parameters.eccentricity * np.sin(ratio * theta)

    derivative_x = (generating_circle_radius + rolling_circle_radius) * (
        -np.sin(theta) + (parameters.eccentricity / rolling_circle_radius) * np.sin(ratio * theta)
    )
    derivative_y = (generating_circle_radius + rolling_circle_radius) * (
        np.cos(theta) - (parameters.eccentricity / rolling_circle_radius) * np.cos(ratio * theta)
    )

    x = x_base + outer_pin_radius * (-derivative_y) / np.sqrt(derivative_x**2 + derivative_y**2)
    y = y_base + outer_pin_radius * derivative_x / np.sqrt(derivative_x**2 + derivative_y**2)
    rotation = -phi / (pin_count - 1) - phi / (pin_count + 1) + np.pi / (pin_count - 1)
    return _rotate_points(x, y, rotation)


def _build_hypocycloid_b(parameters: DriveParameters, pin_count: int, theta: np.ndarray) -> np.ndarray:
    pitch_circle_radius = parameters.pitch_circle_radius
    outer_pin_radius = parameters.outer_pin_radius
    rolling_circle_radius = pitch_circle_radius / pin_count
    generating_circle_radius = (pin_count + 1) * rolling_circle_radius
    ratio = (generating_circle_radius - rolling_circle_radius) / rolling_circle_radius

    x_base = (generating_circle_radius - rolling_circle_radius) * np.cos(theta) + parameters.eccentricity * np.cos(ratio * theta)
    y_base = (generating_circle_radius - rolling_circle_radius) * np.sin(theta) - parameters.eccentricity * np.sin(ratio * theta)

    derivative_x = (generating_circle_radius - rolling_circle_radius) * (
        -np.sin(theta) - (parameters.eccentricity / rolling_circle_radius) * np.sin(ratio * theta)
    )
    derivative_y = (generating_circle_radius - rolling_circle_radius) * (
        np.cos(theta) - (parameters.eccentricity / rolling_circle_radius) * np.cos(ratio * theta)
    )

    x = x_base - outer_pin_radius * (-derivative_y) / np.sqrt(derivative_x**2 + derivative_y**2)
    y = y_base - outer_pin_radius * derivative_x / np.sqrt(derivative_x**2 + derivative_y**2)
    return np.column_stack((x, y))


def _rotate_points(x_values: np.ndarray, y_values: np.ndarray, angle: float) -> np.ndarray:
    x_rotated = x_values * np.cos(angle) - y_values * np.sin(angle)
    y_rotated = x_values * np.sin(angle) + y_values * np.cos(angle)
    return np.column_stack((x_rotated, y_rotated))


def _rotate_point(x_value: float, y_value: float, angle: float) -> tuple[float, float]:
    x_rotated = x_value * np.cos(angle) - y_value * np.sin(angle)
    y_rotated = x_value * np.sin(angle) + y_value * np.cos(angle)
    return (float(x_rotated), float(y_rotated))

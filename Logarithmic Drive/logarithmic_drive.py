from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import subprocess
import sys

import numpy as np

try:
    import ezdxf
except ImportError:  # pragma: no cover - installed by the shared launcher at runtime.
    ezdxf = None

SHARED_UTILS_DIR = Path(__file__).resolve().parents[1]
if str(SHARED_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_UTILS_DIR))

from export_naming import build_export_path


DEFAULT_CURVE_SAMPLE_COUNT = 4400
DEFAULT_SCAN_COUNT = 3600
DEFAULT_CIRCLE_SAMPLE_COUNT = 180
DEFAULT_EXPORT_FOLDER_NAME = "Logarithmic Drive Exports"
DXF_UNITS_LABEL = "DXF units: millimeters (mm)."
MODE_LABEL = "Operating mode: red elliptical input, blue logarithmic output groove, ball-bearing reduction."


@dataclass(frozen=True)
class LogarithmicParameters:
    animation_frames: int
    cusp_count: int
    minor_axis_radius: float
    ball_radius: float
    clearance: float
    show_every_other: bool = False
    input_track_short_width: float | None = None

    @property
    def major_axis_radius(self) -> float:
        return self.minor_axis_radius * self.cusp_count / max(self.cusp_count - 2, 1)

    @property
    def input_track_short_axis_radius(self) -> float:
        requested_width = self.input_track_short_width
        if requested_width is None:
            requested_width = 2.0 * self.minor_axis_radius
        return min(max(0.5 * requested_width, 1e-6), self.major_axis_radius)

    @property
    def input_track_short_axis_width(self) -> float:
        return 2.0 * self.input_track_short_axis_radius

    @property
    def rolling_radius(self) -> float:
        return 0.5 * (self.major_axis_radius - self.input_track_short_axis_radius)

    @property
    def retaining_circle_radius(self) -> float:
        return 0.5 * (self.major_axis_radius + self.minor_axis_radius)

    @property
    def base_circle_radius(self) -> float:
        return self.major_axis_radius

    @property
    def ball_count(self) -> int:
        return max(int(round(self.reduction_ratio - 1.0)), 1)

    @property
    def hole_radius(self) -> float:
        return self.ball_radius + self.rolling_radius

    @property
    def reduction_ratio(self) -> float:
        return self.cusp_count / 2.0

    @property
    def output_tracing_radius(self) -> float:
        return self.ball_radius + 0.5 * self.rolling_radius

    @property
    def output_groove_half_width(self) -> float:
        return self.ball_radius + self.clearance

    @property
    def slot_length(self) -> float:
        return max(self.ball_radius * 3.0, 2.0 * (self.rolling_radius + self.ball_radius + self.clearance))

    @property
    def slot_width(self) -> float:
        return max(self.ball_radius * 1.55, self.ball_radius * 2.0 - 0.35)


@dataclass(frozen=True)
class SceneGeometry:
    ellipse_outline: np.ndarray
    hypocycloid_outline: np.ndarray
    output_trochoid_outline: np.ndarray
    slot_outlines: list[np.ndarray]
    hole_circles: list[np.ndarray]
    ball_circles: list[np.ndarray]
    hole_centers: list[tuple[float, float]]
    ball_centers: list[tuple[float, float]]
    reduction_ratio: float
    mode_label: str


def default_export_directory(fallback_root: Path | None = None) -> Path:
    desktop_directory = Path.home() / "Desktop"
    if desktop_directory.exists():
        return desktop_directory / DEFAULT_EXPORT_FOLDER_NAME

    root = fallback_root or Path.cwd()
    return root / "exports"


def reveal_in_finder(path: Path, runner=subprocess.run) -> None:
    runner(["open", "-R", str(path)], check=True)


def resolve_motion(parameters: LogarithmicParameters, input_angle: float) -> tuple[float, float]:
    output_angle = input_angle / max(parameters.reduction_ratio, 1.0)
    return input_angle, output_angle


def build_scene_geometry(
    parameters: LogarithmicParameters,
    input_angle: float,
    curve_sample_count: int = DEFAULT_CURVE_SAMPLE_COUNT,
    scan_count: int = DEFAULT_SCAN_COUNT,
    circle_sample_count: int = DEFAULT_CIRCLE_SAMPLE_COUNT,
) -> SceneGeometry:
    input_rotation, output_rotation = resolve_motion(parameters, input_angle)
    station_angles = _station_angles(parameters)
    ball_radii = _ball_center_radii(parameters, input_rotation, station_angles)

    ellipse_outline = transform_outline(_sample_ellipse_outline(parameters, curve_sample_count), rotation=input_rotation)
    hypocycloid_outline = _build_station_profile(station_angles, ball_radii, curve_sample_count)
    output_trochoid_outline = transform_outline(
        _build_output_track_profile(parameters, curve_sample_count),
        rotation=output_rotation,
    )
    hole_centers_local = _hole_centers_local(parameters)

    slot_outlines = []
    hole_circles = []
    ball_circles = []
    hole_centers = []
    ball_centers = []

    for center in hole_centers_local:
        world_center = center
        hole_centers.append(world_center)
        slot_outlines.append(
            sample_capsule_points(
                world_center,
                parameters.slot_length,
                parameters.slot_width,
                float(np.arctan2(world_center[1], world_center[0])),
                sample_count=max(circle_sample_count, 64),
            )
        )
        hole_circles.append(sample_circle_points(world_center, parameters.hole_radius, circle_sample_count))

    for station_angle, radius in zip(station_angles, ball_radii, strict=False):
        world_center = _polar_to_xy(radius, station_angle)
        ball_centers.append(world_center)
        ball_circles.append(sample_circle_points(world_center, parameters.ball_radius, circle_sample_count))

    return SceneGeometry(
        ellipse_outline=ellipse_outline,
        hypocycloid_outline=hypocycloid_outline,
        output_trochoid_outline=output_trochoid_outline,
        slot_outlines=slot_outlines,
        hole_circles=hole_circles,
        ball_circles=ball_circles,
        hole_centers=hole_centers,
        ball_centers=ball_centers,
        reduction_ratio=parameters.reduction_ratio,
        mode_label=MODE_LABEL,
    )


def export_scene_to_dxf(
    parameters: LogarithmicParameters,
    input_angle: float,
    output_dir: Path | None = None,
    exported_at: datetime | None = None,
    include_output_trochoid: bool = True,
    file_name: str | None = None,
    include_input_ellipse: bool = True,
    include_station_profile: bool = True,
    include_holes: bool = True,
    include_balls: bool = True,
) -> Path:
    if ezdxf is None:
        raise RuntimeError("DXF export requires the ezdxf package.")

    geometry = build_scene_geometry(parameters, input_angle=input_angle)
    target_directory = Path(output_dir) if output_dir is not None else default_export_directory(Path(__file__).resolve().parent)
    target_directory.mkdir(parents=True, exist_ok=True)

    output_path = build_export_path(
        target_directory,
        default_stem="logarithmic-drive",
        exported_at=exported_at,
        file_name=file_name,
    )

    document = ezdxf.new(setup=True)
    document.units = ezdxf.units.MM
    modelspace = document.modelspace()
    _add_layers(document)

    if include_input_ellipse:
        modelspace.add_lwpolyline(geometry.ellipse_outline.tolist(), close=True, dxfattribs={"layer": "input_ellipse"})
    if include_station_profile:
        modelspace.add_lwpolyline(geometry.hypocycloid_outline.tolist(), close=True, dxfattribs={"layer": "output_profile"})
    if include_output_trochoid:
        modelspace.add_lwpolyline(geometry.output_trochoid_outline.tolist(), close=True, dxfattribs={"layer": "output_trochoid"})

    if include_holes:
        for slot_outline in geometry.slot_outlines:
            modelspace.add_lwpolyline(slot_outline.tolist(), close=True, dxfattribs={"layer": "modulator_slots"})
    if include_balls:
        for center in geometry.ball_centers:
            modelspace.add_circle(center, parameters.ball_radius, dxfattribs={"layer": "balls"})

    document.saveas(output_path)
    return output_path


def export_split_scene_to_dxf(
    parameters: LogarithmicParameters,
    input_angle: float,
    output_dir: Path | None = None,
    exported_at: datetime | None = None,
    input_file_name: str | None = None,
    output_file_name: str | None = None,
) -> tuple[Path, Path]:
    input_path = export_scene_to_dxf(
        parameters,
        input_angle=input_angle,
        output_dir=output_dir,
        exported_at=exported_at,
        include_output_trochoid=False,
        include_input_ellipse=True,
        include_station_profile=False,
        include_holes=True,
        include_balls=True,
        file_name=input_file_name,
    )
    output_path = export_scene_to_dxf(
        parameters,
        input_angle=input_angle,
        output_dir=output_dir,
        exported_at=exported_at,
        include_output_trochoid=True,
        include_input_ellipse=False,
        include_station_profile=False,
        include_holes=False,
        include_balls=False,
        file_name=output_file_name,
    )
    return input_path, output_path


def sample_circle_points(
    center: tuple[float, float],
    radius: float,
    sample_count: int = DEFAULT_CIRCLE_SAMPLE_COUNT,
) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * np.pi, sample_count)
    return np.column_stack((center[0] + radius * np.cos(theta), center[1] + radius * np.sin(theta)))


def sample_capsule_points(
    center: tuple[float, float],
    length: float,
    width: float,
    rotation: float,
    sample_count: int = DEFAULT_CIRCLE_SAMPLE_COUNT,
) -> np.ndarray:
    half_width = max(width * 0.5, 1e-6)
    half_length = max(length * 0.5, half_width + 1e-6)
    straight_half = max(half_length - half_width, 1e-6)
    cap_samples = max(sample_count // 2, 24)
    right_angles = np.linspace(-0.5 * np.pi, 0.5 * np.pi, cap_samples // 2, endpoint=False)
    left_angles = np.linspace(0.5 * np.pi, 1.5 * np.pi, cap_samples // 2, endpoint=False)
    right_cap = np.column_stack(
        (
            straight_half + half_width * np.cos(right_angles),
            half_width * np.sin(right_angles),
        )
    )
    left_cap = np.column_stack(
        (
            -straight_half + half_width * np.cos(left_angles),
            half_width * np.sin(left_angles),
        )
    )
    outline = np.vstack((right_cap, left_cap, right_cap[:1]))
    return transform_outline(outline, center=center, rotation=rotation)


def transform_outline(points: np.ndarray, center: tuple[float, float] = (0.0, 0.0), rotation: float = 0.0) -> np.ndarray:
    rotated = _rotate_points(points, rotation)
    translated = rotated.copy()
    translated[:, 0] += center[0]
    translated[:, 1] += center[1]
    return translated


@lru_cache(maxsize=48)
def _sample_ellipse_outline(parameters: LogarithmicParameters, sample_count: int) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False)
    points = np.column_stack(
        (
            parameters.major_axis_radius * np.cos(theta),
            parameters.input_track_short_axis_radius * np.sin(theta),
        )
    )
    return np.vstack((points, points[0]))


@lru_cache(maxsize=48)
def _sample_hypocycloid_outline(parameters: LogarithmicParameters, sample_count: int) -> np.ndarray:
    t = np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False)
    x_values, y_values = _hypocycloid_xy(parameters, t, lobe_count=parameters.ball_count)
    points = np.column_stack((x_values, y_values))
    return np.vstack((points, points[0]))


def _hole_centers_local(parameters: LogarithmicParameters) -> list[tuple[float, float]]:
    hole_angles = _station_angles(parameters)
    return [
        _polar_to_xy(parameters.retaining_circle_radius, angle)
        for angle in hole_angles
    ]


def _ellipse_radius_at_angle(parameters: LogarithmicParameters, angle: float) -> float:
    short_axis_radius = parameters.input_track_short_axis_radius
    numerator = parameters.major_axis_radius * short_axis_radius
    denominator = np.sqrt(
        (short_axis_radius * np.cos(angle)) ** 2
        + (parameters.major_axis_radius * np.sin(angle)) ** 2
    )
    return float(numerator / max(denominator, 1e-9))


def _build_station_profile(station_angles: np.ndarray, station_radii: np.ndarray, sample_count: int) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False)
    radius = np.array([_catmull_rom_radius(station_radii, angle) for angle in theta], dtype=float)
    points = np.column_stack((radius * np.cos(theta), radius * np.sin(theta)))
    return np.vstack((points, points[0]))


def _build_output_track_profile(
    parameters: LogarithmicParameters,
    sample_count: int,
) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False)
    radius = np.array(
        [
            _ellipse_radius_at_angle(parameters, parameters.reduction_ratio * float(angle))
            for angle in theta
        ],
        dtype=float,
    )
    points = np.column_stack((radius * np.cos(theta), radius * np.sin(theta)))
    return np.vstack((points, points[0]))


def _catmull_rom_radius(station_radii: np.ndarray, angle: float) -> float:
    count = len(station_radii)
    if count == 0:
        return 0.0
    if count == 1:
        return float(station_radii[0])

    delta = 2.0 * np.pi / count
    normalized_angle = float(np.mod(angle, 2.0 * np.pi))
    segment_index = int(np.floor(normalized_angle / delta)) % count
    local_t = (normalized_angle - segment_index * delta) / delta

    p0 = float(station_radii[(segment_index - 1) % count])
    p1 = float(station_radii[segment_index % count])
    p2 = float(station_radii[(segment_index + 1) % count])
    p3 = float(station_radii[(segment_index + 2) % count])

    return float(
        0.5
        * (
            (2.0 * p1)
            + (-p0 + p2) * local_t
            + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * (local_t**2)
            + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * (local_t**3)
        )
    )


def _hypocycloid_xy(
    parameters: LogarithmicParameters,
    t_values: np.ndarray,
    lobe_count: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    target_lobes = max(int(lobe_count or parameters.cusp_count), 1)
    base_radius = parameters.base_circle_radius
    rolling_radius = base_radius / target_lobes
    ratio = (base_radius - rolling_radius) / max(rolling_radius, 1e-9)
    x_values = (base_radius - rolling_radius) * np.cos(t_values) + rolling_radius * np.cos(ratio * t_values)
    y_values = (base_radius - rolling_radius) * np.sin(t_values) - rolling_radius * np.sin(ratio * t_values)
    return x_values, y_values


@lru_cache(maxsize=48)
def _optimal_output_track_transform(parameters: LogarithmicParameters) -> tuple[float, float, float]:
    return 1.0, 0.0, 0.0


def _station_angles(parameters: LogarithmicParameters) -> np.ndarray:
    return np.linspace(0.0, 2.0 * np.pi, parameters.ball_count, endpoint=False)


def _ball_center_radii(
    parameters: LogarithmicParameters,
    input_rotation: float,
    station_angles: np.ndarray,
) -> np.ndarray:
    return np.array(
        [
            _ellipse_radius_at_angle(parameters, float(station_angle - input_rotation))
            for station_angle in station_angles
        ],
        dtype=float,
    )


def _polar_to_xy(radius: float, angle: float) -> tuple[float, float]:
    return (
        float(radius * np.cos(angle)),
        float(radius * np.sin(angle)),
    )


def _rotate_points(points: np.ndarray, angle: float) -> np.ndarray:
    cosine = np.cos(angle)
    sine = np.sin(angle)
    x_values = points[:, 0] * cosine - points[:, 1] * sine
    y_values = points[:, 0] * sine + points[:, 1] * cosine
    return np.column_stack((x_values, y_values))


def _rotate_point(point: tuple[float, float], angle: float) -> tuple[float, float]:
    cosine = float(np.cos(angle))
    sine = float(np.sin(angle))
    return (
        float(point[0] * cosine - point[1] * sine),
        float(point[0] * sine + point[1] * cosine),
    )


def _add_layers(document) -> None:
    layers = (
        ("input_ellipse", 1),
        ("output_profile", 5),
        ("output_trochoid", 5),
        ("modulator_slots", 8),
        ("retaining_holes", 8),
        ("balls", 3),
    )

    for name, color in layers:
        if name not in document.layers:
            document.layers.add(name, color=color)

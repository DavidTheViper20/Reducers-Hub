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
PLANETARY_DIR = SHARED_UTILS_DIR / "Planetary"
if str(PLANETARY_DIR) not in sys.path:
    sys.path.insert(0, str(PLANETARY_DIR))

from export_naming import build_export_path
from planetary_drive import _build_external_gear_outline, _build_internal_ring_outline


DEFAULT_SAMPLE_COUNT = 2400
DEFAULT_CIRCLE_SAMPLE_COUNT = 220
DEFAULT_EXPORT_FOLDER_NAME = "Harmonic Drive Exports"
DXF_UNITS_LABEL = "DXF units: millimeters (mm)."
MODE_LABEL = "Operating mode: red wave generator input, blue circular spline fixed, green flex spline output."
FLEX_TOOTH_PHASE_BIAS = 0.0


@dataclass(frozen=True)
class HarmonicParameters:
    animation_frames: int
    module: float
    flex_teeth: int
    circular_teeth: int
    tooth_depth: float
    wave_generator_thickness: float
    bore_radius: float
    pressure_angle_degrees: float

    def __post_init__(self) -> None:
        if self.circular_teeth - self.flex_teeth != 2:
            object.__setattr__(self, "flex_teeth", self.circular_teeth - 2)

    @property
    def tooth_difference(self) -> int:
        return 2

    @property
    def reduction_ratio(self) -> float:
        return self.flex_teeth / self.tooth_difference

    @property
    def pressure_angle_radians(self) -> float:
        return float(np.deg2rad(self.pressure_angle_degrees))

    @property
    def pressure_shape_factor(self) -> float:
        normalized = (self.pressure_angle_degrees - 10.0) / 25.0
        return float(np.clip(normalized, 0.0, 1.0))

    @property
    def circular_pitch_radius(self) -> float:
        return self.module * self.circular_teeth / 2.0

    @property
    def flex_pitch_radius(self) -> float:
        return self.module * self.flex_teeth / 2.0

    @property
    def ring_inner_base_radius(self) -> float:
        return self.circular_pitch_radius

    @property
    def flex_base_radius(self) -> float:
        return self.flex_pitch_radius

    @property
    def circular_body_radius(self) -> float:
        return self.ring_inner_base_radius + self.tooth_depth * 2.6

    @property
    def addendum(self) -> float:
        return max(self.module * 0.46, self.tooth_depth * 0.34)

    @property
    def dedendum(self) -> float:
        return max(self.module * 0.58, self.tooth_depth * 0.44)

    @property
    def flex_addendum(self) -> float:
        return self.addendum * (0.80 - 0.05 * self.pressure_shape_factor)

    @property
    def flex_dedendum(self) -> float:
        return self.dedendum * (0.82 - 0.04 * self.pressure_shape_factor)

    @property
    def flex_ring_thickness(self) -> float:
        return max(self.module * 1.35, self.tooth_depth * 1.45)

    @property
    def wave_amplitude(self) -> float:
        mesh_clearance = max(self.module * 0.016, 0.025)
        ring_contact_offset = self.tooth_depth * self.ring_contact_factor
        flex_contact_offset = self.tooth_depth * self.flex_contact_factor
        return max(
            self.module * 1.12 + self.tooth_depth * 0.10,
            self.ring_inner_base_radius + ring_contact_offset - self.flex_base_radius - flex_contact_offset - mesh_clearance,
        )

    @property
    def contact_clearance(self) -> float:
        return max(self.module * 0.034, 0.055)

    @property
    def tooth_profile_power(self) -> float:
        return 1.65 + 2.10 * self.pressure_shape_factor

    @property
    def ring_mean_factor(self) -> float:
        return 0.26 - 0.02 * self.pressure_shape_factor

    @property
    def ring_swing_factor(self) -> float:
        return 0.96 - 0.08 * self.pressure_shape_factor

    @property
    def flex_mean_factor(self) -> float:
        return 0.04 + 0.01 * self.pressure_shape_factor

    @property
    def flex_swing_factor(self) -> float:
        return 0.64 - 0.03 * self.pressure_shape_factor

    @property
    def ring_contact_factor(self) -> float:
        return self.ring_mean_factor - self.ring_swing_factor

    @property
    def flex_contact_factor(self) -> float:
        return self.flex_mean_factor + self.flex_swing_factor

    @property
    def flex_inner_major_axis(self) -> float:
        return max(
            self.bore_radius + self.tooth_depth * 1.45,
            self.wave_generator_outer_major_axis + self.contact_clearance * 0.5,
        )

    @property
    def flex_inner_minor_axis(self) -> float:
        return max(
            self.bore_radius + self.tooth_depth * 1.05,
            self.wave_generator_outer_minor_axis + self.contact_clearance * 0.5,
        )

    @property
    def wave_generator_outer_major_axis(self) -> float:
        base_radius = self.flex_base_radius - self.flex_ring_thickness + self.wave_amplitude * 0.90
        return max(self.bore_radius + self.tooth_depth * 0.72, base_radius)

    @property
    def wave_generator_outer_minor_axis(self) -> float:
        base_radius = self.flex_base_radius - self.flex_ring_thickness - self.wave_amplitude * 1.04
        compression = self.wave_generator_thickness * 0.58
        return max(self.bore_radius + self.tooth_depth * 0.62, base_radius - compression)

    @property
    def wave_generator_wall_thickness(self) -> float:
        return max(self.module * 0.54, self.tooth_depth * 0.46)

    @property
    def wave_generator_inner_major_axis(self) -> float:
        return max(self.bore_radius + self.tooth_depth * 0.25, self.wave_generator_outer_major_axis - self.wave_generator_wall_thickness)

    @property
    def wave_generator_inner_minor_axis(self) -> float:
        return max(self.bore_radius + self.tooth_depth * 0.18, self.wave_generator_outer_minor_axis - self.wave_generator_wall_thickness)


@dataclass(frozen=True)
class SceneGeometry:
    circular_spline_outline: np.ndarray
    circular_body_outline: np.ndarray
    flex_spline_outline: np.ndarray
    flex_inner_outline: np.ndarray
    wave_generator_outline: np.ndarray
    wave_generator_inner_outline: np.ndarray
    bore_circle: np.ndarray
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


def resolve_motion(parameters: HarmonicParameters, input_angle: float) -> tuple[float, float]:
    flex_angle = -input_angle / max(parameters.reduction_ratio, 1.0)
    return input_angle, flex_angle


def build_scene_geometry(
    parameters: HarmonicParameters,
    input_angle: float,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    circle_sample_count: int = DEFAULT_CIRCLE_SAMPLE_COUNT,
) -> SceneGeometry:
    wave_angle, flex_angle = resolve_motion(parameters, input_angle)
    circular_outline = _build_internal_ring_outline(
        pitch_radius=parameters.circular_pitch_radius,
        teeth=parameters.circular_teeth,
        addendum=parameters.addendum,
        dedendum=parameters.dedendum,
        pressure_angle=parameters.pressure_angle_radians,
        sample_count=sample_count,
    )
    circular_body_outline = _sample_circle(parameters.circular_body_radius, sample_count)

    flex_phase_trim = _optimal_flex_phase_trim(parameters)
    flex_base_outline = _build_external_gear_outline(
        pitch_radius=parameters.flex_pitch_radius,
        teeth=parameters.flex_teeth,
        addendum=parameters.flex_addendum,
        dedendum=parameters.flex_dedendum,
        pressure_angle=parameters.pressure_angle_radians,
        sample_count=sample_count,
    )
    flex_outline = _deform_flex_outline(
        flex_base_outline,
        wave_angle=wave_angle,
        body_rotation=flex_angle + flex_phase_trim + FLEX_TOOTH_PHASE_BIAS * (2.0 * np.pi / max(parameters.flex_teeth, 1)),
        parameters=parameters,
    )
    flex_inner_outline = _sample_ellipse(
        parameters.flex_inner_major_axis,
        parameters.flex_inner_minor_axis,
        rotation=wave_angle,
        sample_count=circle_sample_count,
    )

    wave_generator_outline = _sample_ellipse(
        parameters.wave_generator_outer_major_axis,
        parameters.wave_generator_outer_minor_axis,
        rotation=wave_angle,
        sample_count=circle_sample_count,
    )
    wave_generator_inner_outline = _sample_ellipse(
        parameters.wave_generator_inner_major_axis,
        parameters.wave_generator_inner_minor_axis,
        rotation=wave_angle,
        sample_count=circle_sample_count,
    )
    bore_circle = _sample_circle(parameters.bore_radius, sample_count=circle_sample_count)

    return SceneGeometry(
        circular_spline_outline=np.vstack((circular_outline, circular_outline[0])) if not np.allclose(circular_outline[0], circular_outline[-1]) else circular_outline.copy(),
        circular_body_outline=np.vstack((circular_body_outline, circular_body_outline[0])),
        flex_spline_outline=np.vstack((flex_outline, flex_outline[0])) if not np.allclose(flex_outline[0], flex_outline[-1]) else flex_outline.copy(),
        flex_inner_outline=np.vstack((flex_inner_outline, flex_inner_outline[0])),
        wave_generator_outline=np.vstack((wave_generator_outline, wave_generator_outline[0])),
        wave_generator_inner_outline=np.vstack((wave_generator_inner_outline, wave_generator_inner_outline[0])),
        bore_circle=np.vstack((bore_circle, bore_circle[0])),
        reduction_ratio=parameters.reduction_ratio,
        mode_label=MODE_LABEL,
    )


def export_scene_to_dxf(
    parameters: HarmonicParameters,
    input_angle: float,
    output_dir: Path | None = None,
    exported_at: datetime | None = None,
    file_name: str | None = None,
) -> Path:
    if ezdxf is None:
        raise RuntimeError("DXF export requires the ezdxf package.")

    geometry = build_scene_geometry(parameters, input_angle=input_angle)
    target_directory = Path(output_dir) if output_dir is not None else default_export_directory(Path(__file__).resolve().parent)
    target_directory.mkdir(parents=True, exist_ok=True)

    output_path = build_export_path(
        target_directory,
        default_stem="harmonic-drive",
        exported_at=exported_at,
        file_name=file_name,
    )

    document = ezdxf.new(setup=True)
    document.units = ezdxf.units.MM
    modelspace = document.modelspace()
    _add_layers(document)

    modelspace.add_lwpolyline(geometry.circular_spline_outline.tolist(), close=True, dxfattribs={"layer": "circular_spline"})
    modelspace.add_lwpolyline(geometry.circular_body_outline.tolist(), close=True, dxfattribs={"layer": "circular_body"})
    modelspace.add_lwpolyline(geometry.flex_spline_outline.tolist(), close=True, dxfattribs={"layer": "flex_spline"})
    modelspace.add_lwpolyline(geometry.flex_inner_outline.tolist(), close=True, dxfattribs={"layer": "flex_inner"})
    modelspace.add_lwpolyline(geometry.wave_generator_outline.tolist(), close=True, dxfattribs={"layer": "wave_generator"})
    modelspace.add_lwpolyline(geometry.wave_generator_inner_outline.tolist(), close=True, dxfattribs={"layer": "wave_generator"})
    modelspace.add_circle((0.0, 0.0), parameters.bore_radius, dxfattribs={"layer": "bore"})

    document.saveas(output_path)
    return output_path


def _polar_outline(theta: np.ndarray, radius: np.ndarray) -> np.ndarray:
    return np.column_stack((radius * np.cos(theta), radius * np.sin(theta)))


def _sample_ellipse(major_axis: float, minor_axis: float, rotation: float, sample_count: int) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False)
    points = np.column_stack((major_axis * np.cos(theta), minor_axis * np.sin(theta)))
    return _rotate_points(points, rotation)


def _sample_circle(radius: float, sample_count: int) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False)
    return np.column_stack((radius * np.cos(theta), radius * np.sin(theta)))


def _shaped_tooth_wave(angle: np.ndarray, sharpness: float) -> np.ndarray:
    primary = np.cos(angle)
    crest = 0.34 * np.cos(3.0 * angle)
    shoulder = -0.10 * np.cos(5.0 * angle)
    blended = np.clip((primary + crest + shoulder) / 1.24, -1.0, 1.0)
    return np.sign(blended) * np.abs(blended) ** sharpness


@lru_cache(maxsize=64)
def _optimal_flex_phase_trim(parameters: HarmonicParameters) -> float:
    circular_outline = _build_internal_ring_outline(
        pitch_radius=parameters.circular_pitch_radius,
        teeth=parameters.circular_teeth,
        addendum=parameters.addendum,
        dedendum=parameters.dedendum,
        pressure_angle=parameters.pressure_angle_radians,
        sample_count=DEFAULT_SAMPLE_COUNT,
    )
    flex_base_outline = _build_external_gear_outline(
        pitch_radius=parameters.flex_pitch_radius,
        teeth=parameters.flex_teeth,
        addendum=parameters.flex_addendum,
        dedendum=parameters.flex_dedendum,
        pressure_angle=parameters.pressure_angle_radians,
        sample_count=DEFAULT_SAMPLE_COUNT,
    )
    pitch = 2.0 * np.pi / max(parameters.flex_teeth, 1)
    circular_angles, circular_radii = _outline_polar_profile(circular_outline)
    contact_offsets = np.linspace(-0.22, 0.22, 17)
    contact_angles = np.concatenate((contact_offsets, np.pi + contact_offsets))
    contact_weights = np.concatenate((
        np.cos(0.5 * contact_offsets / 0.22) ** 2,
        np.cos(0.5 * contact_offsets / 0.22) ** 2,
    ))
    relief_angles = np.array([0.5 * np.pi, 1.5 * np.pi], dtype=float)
    contact_target = parameters.contact_clearance * 0.10
    relief_target = parameters.wave_amplitude * 1.75 + parameters.contact_clearance
    best_error = float("inf")
    best_trim = 0.0

    for phase_trim in np.linspace(0.0, pitch, 181):
        flex_outline = _deform_flex_outline(
            flex_base_outline,
            wave_angle=0.0,
            body_rotation=phase_trim,
            parameters=parameters,
        )
        flex_angles, flex_radii = _outline_polar_profile(flex_outline)
        contact_gap = np.array(
            [
                _radius_at_angle(circular_angles, circular_radii, angle) - _radius_at_angle(flex_angles, flex_radii, angle)
                for angle in contact_angles
            ],
            dtype=float,
        )
        relief_gap = np.array(
            [
                _radius_at_angle(circular_angles, circular_radii, angle) - _radius_at_angle(flex_angles, flex_radii, angle)
                for angle in relief_angles
            ],
            dtype=float,
        )
        error = float(np.sum(contact_weights * (contact_gap - contact_target) ** 2) + 0.05 * np.sum((relief_gap - relief_target) ** 2))
        if error < best_error:
            best_error = error
            best_trim = float(phase_trim)

    return best_trim


def _deform_flex_outline(
    base_outline: np.ndarray,
    wave_angle: float,
    body_rotation: float,
    parameters: HarmonicParameters,
) -> np.ndarray:
    rotated = _rotate_points(base_outline, body_rotation)
    theta = np.arctan2(rotated[:, 1], rotated[:, 0])
    radius = np.hypot(rotated[:, 0], rotated[:, 1])
    radial_shift = parameters.wave_amplitude * np.cos(2.0 * (theta - wave_angle))
    angular_shift = (
        parameters.wave_amplitude
        / max(parameters.flex_pitch_radius, 1e-9)
        * 0.14
        * np.sin(2.0 * (theta - wave_angle))
    )
    warped_theta = theta + angular_shift
    deformed_radius = radius + radial_shift
    return np.column_stack((deformed_radius * np.cos(warped_theta), deformed_radius * np.sin(warped_theta)))


def _outline_polar_profile(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    outline = points[:-1] if np.allclose(points[0], points[-1]) else points
    angles = np.mod(np.arctan2(outline[:, 1], outline[:, 0]), 2.0 * np.pi)
    radii = np.hypot(outline[:, 0], outline[:, 1])
    order = np.argsort(angles)
    sorted_angles = angles[order]
    sorted_radii = radii[order]
    return (
        np.concatenate((sorted_angles, sorted_angles[:1] + 2.0 * np.pi)),
        np.concatenate((sorted_radii, sorted_radii[:1])),
    )


def _radius_at_angle(angles: np.ndarray, radii: np.ndarray, angle: float) -> float:
    return float(np.interp(float(np.mod(angle, 2.0 * np.pi)), angles, radii))


def _rotate_points(points: np.ndarray, angle: float) -> np.ndarray:
    cosine = np.cos(angle)
    sine = np.sin(angle)
    x_values = points[:, 0] * cosine - points[:, 1] * sine
    y_values = points[:, 0] * sine + points[:, 1] * cosine
    return np.column_stack((x_values, y_values))


def _add_layers(document) -> None:
    layers = (
        ("circular_spline", 5),
        ("circular_body", 8),
        ("flex_spline", 3),
        ("flex_inner", 3),
        ("wave_generator", 1),
        ("bore", 7),
    )

    for name, color in layers:
        if name not in document.layers:
            document.layers.add(name, color=color)

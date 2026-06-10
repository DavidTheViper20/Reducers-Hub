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


DEFAULT_GEAR_SAMPLE_COUNT = 960
DEFAULT_CIRCLE_SAMPLE_COUNT = 240
DEFAULT_EXPORT_FOLDER_NAME = "Planetary Gear Exports"
DXF_UNITS_LABEL = "DXF units: millimeters (mm)."
DEFAULT_MODE_KEY = "fixed_ring_sun_input"
MODE_LABEL = "Operating mode: fixed ring, sun input, carrier output."
DEFAULT_TOOTH_DEPTH = 2.6
DEFAULT_PRESSURE_ANGLE_DEGREES = 20.0
DEFAULT_BACKLASH_FACTOR = 0.08
PLANET_PHASE_TRIM = 0.0


@dataclass(frozen=True)
class PlanetaryModeSpec:
    key: str
    title: str
    mode_label: str
    description: str
    export_stem: str
    ratio_label: str


PLANETARY_MODE_SPECS: dict[str, PlanetaryModeSpec] = {
    "fixed_ring_sun_input": PlanetaryModeSpec(
        key="fixed_ring_sun_input",
        title="Fixed-Ring Planetary Reducer",
        mode_label="Operating mode: fixed ring, sun input, carrier output.",
        description="The blue internal ring is locked, the red sun gear drives the set, and the gray carrier arms orbit with the green planet gears.",
        export_stem="planetary-fixed-ring",
        ratio_label="Reduction Ratio",
    ),
    "fixed_carrier_ring_input": PlanetaryModeSpec(
        key="fixed_carrier_ring_input",
        title="Fixed-Carrier Ring-Driven Planetary",
        mode_label="Operating mode: fixed carrier, ring input, sun output.",
        description="The carrier is locked so the planets stay in place while the blue ring drives them and the red sun gear counter-rotates in place.",
        export_stem="planetary-fixed-carrier",
        ratio_label="Ring-to-Sun Speed",
    ),
    "fixed_sun_ring_input": PlanetaryModeSpec(
        key="fixed_sun_ring_input",
        title="Fixed-Sun Ring-Driven Carrier",
        mode_label="Operating mode: fixed sun, ring input, carrier output.",
        description="The red sun gear is locked while the blue ring drives the green planets around it, carrying the gray arm assembly as the output.",
        export_stem="planetary-fixed-sun",
        ratio_label="Ring-to-Carrier Reduction",
    ),
}


@dataclass(frozen=True)
class PlanetaryGeometryKey:
    module: float
    sun_teeth: int
    planet_teeth: int
    tooth_depth: float
    pressure_angle_degrees: float

    @property
    def ring_teeth(self) -> int:
        return int(self.sun_teeth + 2 * self.planet_teeth)

    @property
    def pressure_angle_radians(self) -> float:
        return np.deg2rad(self.pressure_angle_degrees)

    @property
    def tooth_height_scale(self) -> float:
        return max(0.45, self.tooth_depth / DEFAULT_TOOTH_DEPTH)

    @property
    def addendum(self) -> float:
        return self.module * self.tooth_height_scale

    @property
    def dedendum(self) -> float:
        return 1.25 * self.module * self.tooth_height_scale

    @property
    def sun_pitch_radius(self) -> float:
        return self.module * self.sun_teeth / 2.0

    @property
    def planet_pitch_radius(self) -> float:
        return self.module * self.planet_teeth / 2.0

    @property
    def ring_pitch_radius(self) -> float:
        return self.module * self.ring_teeth / 2.0

    @property
    def carrier_radius(self) -> float:
        return self.sun_pitch_radius + self.planet_pitch_radius

    @property
    def sun_root_radius(self) -> float:
        return max(self.sun_pitch_radius - self.dedendum, self.module * 1.2)

    @property
    def sun_tip_radius(self) -> float:
        return self.sun_pitch_radius + self.addendum

    @property
    def planet_root_radius(self) -> float:
        return max(self.planet_pitch_radius - self.dedendum, self.module * 1.0)

    @property
    def planet_tip_radius(self) -> float:
        return self.planet_pitch_radius + self.addendum

    @property
    def ring_tip_radius(self) -> float:
        return max(self.ring_pitch_radius - self.addendum, self.module * 2.0)

    @property
    def ring_root_radius(self) -> float:
        return self.ring_pitch_radius + self.dedendum

    @property
    def ring_outer_radius(self) -> float:
        return self.ring_root_radius + 1.6 * self.module

    @property
    def sun_phase_trim(self) -> float:
        return 0.0


@dataclass(frozen=True)
class PlanetaryParameters:
    animation_frames: int
    module: float
    sun_teeth: int
    planet_teeth: int
    planet_count: int
    tooth_depth: float
    sun_bore_radius: float
    planet_bore_radius: float
    pressure_angle_degrees: float = DEFAULT_PRESSURE_ANGLE_DEGREES

    @property
    def geometry_key(self) -> PlanetaryGeometryKey:
        return PlanetaryGeometryKey(
            module=float(self.module),
            sun_teeth=int(self.sun_teeth),
            planet_teeth=int(self.planet_teeth),
            tooth_depth=float(self.tooth_depth),
            pressure_angle_degrees=float(self.pressure_angle_degrees),
        )

    @property
    def ring_teeth(self) -> int:
        return self.geometry_key.ring_teeth

    @property
    def pressure_angle_radians(self) -> float:
        return self.geometry_key.pressure_angle_radians

    @property
    def tooth_height_scale(self) -> float:
        return self.geometry_key.tooth_height_scale

    @property
    def addendum(self) -> float:
        return self.geometry_key.addendum

    @property
    def dedendum(self) -> float:
        return self.geometry_key.dedendum

    @property
    def sun_pitch_radius(self) -> float:
        return self.geometry_key.sun_pitch_radius

    @property
    def planet_pitch_radius(self) -> float:
        return self.geometry_key.planet_pitch_radius

    @property
    def ring_pitch_radius(self) -> float:
        return self.geometry_key.ring_pitch_radius

    @property
    def carrier_radius(self) -> float:
        return self.geometry_key.carrier_radius

    @property
    def sun_root_radius(self) -> float:
        return self.geometry_key.sun_root_radius

    @property
    def sun_tip_radius(self) -> float:
        return self.geometry_key.sun_tip_radius

    @property
    def planet_root_radius(self) -> float:
        return self.geometry_key.planet_root_radius

    @property
    def planet_tip_radius(self) -> float:
        return self.geometry_key.planet_tip_radius

    @property
    def ring_tip_radius(self) -> float:
        return self.geometry_key.ring_tip_radius

    @property
    def ring_root_radius(self) -> float:
        return self.geometry_key.ring_root_radius

    @property
    def ring_outer_radius(self) -> float:
        return self.geometry_key.ring_outer_radius

    @property
    def sun_phase_trim(self) -> float:
        return self.geometry_key.sun_phase_trim

    @property
    def carrier_hub_radius(self) -> float:
        minimum_radius = self.sun_bore_radius + max(self.module * 1.1, self.planet_bore_radius * 0.3)
        return max(minimum_radius, self.sun_pitch_radius * 0.32)

    @property
    def reduction_ratio(self) -> float:
        return 1.0 + self.ring_teeth / max(self.sun_teeth, 1)


@dataclass(frozen=True)
class MotionState:
    sun_angle: float
    ring_angle: float
    carrier_angle: float
    planet_spin_angle: float
    ratio_value: float


@dataclass(frozen=True)
class SceneGeometry:
    sun_outline: np.ndarray
    ring_inner_outline: np.ndarray
    ring_outer_circle: np.ndarray
    sun_bore_circle: np.ndarray
    planet_outlines: list[np.ndarray]
    planet_bore_circles: list[np.ndarray]
    carrier_arm_segments: list[np.ndarray]
    carrier_hub_circle: np.ndarray
    planet_centers: list[tuple[float, float]]
    effective_planet_count: int
    ring_teeth: int
    ratio_label: str
    ratio_value: float
    mode_label: str


SUN_PHASE_TRIM = PlanetaryGeometryKey(
    module=2.0,
    sun_teeth=18,
    planet_teeth=12,
    tooth_depth=DEFAULT_TOOTH_DEPTH,
    pressure_angle_degrees=DEFAULT_PRESSURE_ANGLE_DEGREES,
).sun_phase_trim


def get_mode_spec(mode_key: str) -> PlanetaryModeSpec:
    try:
        return PLANETARY_MODE_SPECS[mode_key]
    except KeyError as error:
        raise ValueError(f"Unknown planetary mode: {mode_key}") from error


def default_export_directory(fallback_root: Path | None = None) -> Path:
    desktop_directory = Path.home() / "Desktop"
    if desktop_directory.exists():
        return desktop_directory / DEFAULT_EXPORT_FOLDER_NAME

    root = fallback_root or Path.cwd()
    return root / "exports"


def reveal_in_finder(path: Path, runner=subprocess.run) -> None:
    runner(["open", "-R", str(path)], check=True)


def sample_circle_points(
    center: tuple[float, float],
    radius: float,
    sample_count: int = DEFAULT_CIRCLE_SAMPLE_COUNT,
) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * np.pi, sample_count)
    x_values = center[0] + radius * np.cos(theta)
    y_values = center[1] + radius * np.sin(theta)
    return np.column_stack((x_values, y_values))


def resolve_motion(parameters: PlanetaryParameters, mode_key: str, input_angle: float) -> MotionState:
    mode_spec = get_mode_spec(mode_key)
    sun_teeth = max(parameters.sun_teeth, 1)
    planet_teeth = max(parameters.planet_teeth, 1)
    ring_teeth = max(parameters.ring_teeth, 1)

    if mode_spec.key == "fixed_ring_sun_input":
        sun_angle = input_angle
        ring_angle = 0.0
        carrier_angle = input_angle * sun_teeth / (sun_teeth + ring_teeth)
        ratio_value = parameters.reduction_ratio
    elif mode_spec.key == "fixed_carrier_ring_input":
        sun_angle = -input_angle * ring_teeth / sun_teeth
        ring_angle = input_angle
        carrier_angle = 0.0
        ratio_value = ring_teeth / sun_teeth
    elif mode_spec.key == "fixed_sun_ring_input":
        sun_angle = 0.0
        ring_angle = input_angle
        carrier_angle = input_angle * ring_teeth / (sun_teeth + ring_teeth)
        ratio_value = (sun_teeth + ring_teeth) / ring_teeth
    else:  # pragma: no cover - guarded by get_mode_spec
        raise ValueError(f"Unsupported planetary mode: {mode_key}")

    planet_spin_angle = carrier_angle - (sun_teeth / planet_teeth) * (sun_angle - carrier_angle)
    return MotionState(
        sun_angle=sun_angle,
        ring_angle=ring_angle,
        carrier_angle=carrier_angle,
        planet_spin_angle=planet_spin_angle,
        ratio_value=ratio_value,
    )


def build_scene_geometry(
    parameters: PlanetaryParameters,
    input_angle: float,
    mode_key: str = DEFAULT_MODE_KEY,
    gear_sample_count: int = DEFAULT_GEAR_SAMPLE_COUNT,
    circle_sample_count: int = DEFAULT_CIRCLE_SAMPLE_COUNT,
) -> SceneGeometry:
    geometry_key = parameters.geometry_key
    mode_spec = get_mode_spec(mode_key)
    effective_planet_count = effective_planet_count_for_parameters(parameters)
    motion = resolve_motion(parameters, mode_key, input_angle)

    sun_local, planet_local, ring_inner_local = _cached_local_outlines(geometry_key, gear_sample_count)
    ring_outer_local = _cached_circle(parameters.ring_outer_radius, circle_sample_count)
    sun_bore_local = _cached_circle(parameters.sun_bore_radius, circle_sample_count)
    planet_bore_local = _cached_circle(parameters.planet_bore_radius, circle_sample_count)
    carrier_hub_local = _cached_circle(parameters.carrier_hub_radius, circle_sample_count)

    sun_outline = transform_outline(sun_local, rotation=motion.sun_angle + parameters.sun_phase_trim)
    ring_inner_outline = transform_outline(ring_inner_local, rotation=motion.ring_angle)
    ring_outer_circle = transform_outline(ring_outer_local, rotation=motion.ring_angle)

    base_angles = np.linspace(0.0, 2.0 * np.pi, effective_planet_count, endpoint=False)
    phase_offsets = _planet_phase_offsets(geometry_key, effective_planet_count)
    planet_centers = []
    planet_outlines = []
    planet_bore_circles = []
    carrier_arm_segments = []

    for base_angle, phase_offset in zip(base_angles, phase_offsets, strict=False):
        orbital_angle = base_angle + motion.carrier_angle
        center = (
            float(geometry_key.carrier_radius * np.cos(orbital_angle)),
            float(geometry_key.carrier_radius * np.sin(orbital_angle)),
        )
        inner_arm_point = (
            float(parameters.carrier_hub_radius * np.cos(orbital_angle)),
            float(parameters.carrier_hub_radius * np.sin(orbital_angle)),
        )
        planet_centers.append(center)
        planet_outlines.append(
            transform_outline(
                planet_local,
                center=center,
                rotation=motion.planet_spin_angle + phase_offset,
            )
        )
        planet_bore_circles.append(transform_outline(planet_bore_local, center=center))
        carrier_arm_segments.append(np.array([inner_arm_point, center], dtype=float))

    return SceneGeometry(
        sun_outline=sun_outline,
        ring_inner_outline=ring_inner_outline,
        ring_outer_circle=ring_outer_circle,
        sun_bore_circle=sun_bore_local.copy(),
        planet_outlines=planet_outlines,
        planet_bore_circles=planet_bore_circles,
        carrier_arm_segments=carrier_arm_segments,
        carrier_hub_circle=carrier_hub_local.copy(),
        planet_centers=planet_centers,
        effective_planet_count=effective_planet_count,
        ring_teeth=parameters.ring_teeth,
        ratio_label=mode_spec.ratio_label,
        ratio_value=motion.ratio_value,
        mode_label=mode_spec.mode_label,
    )


def effective_planet_count_for_parameters(parameters: PlanetaryParameters) -> int:
    geometry_key = parameters.geometry_key
    requested_count = max(2, int(round(parameters.planet_count)))
    maximum_geometry_count = _maximum_geometry_planet_count(geometry_key)
    compatible_counts = [
        count
        for count in range(2, maximum_geometry_count + 1)
        if (geometry_key.sun_teeth + geometry_key.ring_teeth) % count == 0
    ]

    if compatible_counts:
        return min(compatible_counts, key=lambda count: (abs(count - requested_count), -count))

    return min(requested_count, maximum_geometry_count)


def export_scene_to_dxf(
    parameters: PlanetaryParameters,
    input_angle: float,
    mode_key: str = DEFAULT_MODE_KEY,
    output_dir: Path | None = None,
    exported_at: datetime | None = None,
    include_sun_bore: bool = True,
    include_planet_bores: bool = True,
    file_name: str | None = None,
) -> Path:
    if ezdxf is None:
        raise RuntimeError("DXF export requires the ezdxf package.")

    mode_spec = get_mode_spec(mode_key)
    geometry = build_scene_geometry(parameters, input_angle=input_angle, mode_key=mode_key)
    target_directory = Path(output_dir) if output_dir is not None else default_export_directory(Path(__file__).resolve().parent)
    target_directory.mkdir(parents=True, exist_ok=True)

    output_path = build_export_path(
        target_directory,
        default_stem=mode_spec.export_stem,
        exported_at=exported_at,
        file_name=file_name,
    )

    document = ezdxf.new(setup=True)
    document.units = ezdxf.units.MM
    modelspace = document.modelspace()
    _add_layers(document)

    modelspace.add_lwpolyline(geometry.ring_inner_outline.tolist(), close=True, dxfattribs={"layer": "ring_gear"})
    modelspace.add_lwpolyline(geometry.ring_outer_circle.tolist(), close=True, dxfattribs={"layer": "ring_gear"})
    modelspace.add_lwpolyline(geometry.sun_outline.tolist(), close=True, dxfattribs={"layer": "sun_gear"})
    modelspace.add_lwpolyline(geometry.carrier_hub_circle.tolist(), close=True, dxfattribs={"layer": "carrier"})

    if include_sun_bore:
        modelspace.add_circle((0.0, 0.0), parameters.sun_bore_radius, dxfattribs={"layer": "bores"})

    for outline in geometry.planet_outlines:
        modelspace.add_lwpolyline(outline.tolist(), close=True, dxfattribs={"layer": "planet_gears"})

    if include_planet_bores:
        for center in geometry.planet_centers:
            modelspace.add_circle(center, parameters.planet_bore_radius, dxfattribs={"layer": "bores"})

    document.saveas(output_path)
    return output_path


@lru_cache(maxsize=64)
def _cached_local_outlines(geometry_key: PlanetaryGeometryKey, sample_count: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sun_outline = _build_external_gear_outline(
        pitch_radius=geometry_key.sun_pitch_radius,
        teeth=geometry_key.sun_teeth,
        addendum=geometry_key.addendum,
        dedendum=geometry_key.dedendum,
        pressure_angle=geometry_key.pressure_angle_radians,
        sample_count=sample_count,
    )
    planet_outline = _build_external_gear_outline(
        pitch_radius=geometry_key.planet_pitch_radius,
        teeth=geometry_key.planet_teeth,
        addendum=geometry_key.addendum,
        dedendum=geometry_key.dedendum,
        pressure_angle=geometry_key.pressure_angle_radians,
        sample_count=sample_count,
    )
    ring_inner_outline = _build_internal_ring_outline(
        pitch_radius=geometry_key.ring_pitch_radius,
        teeth=geometry_key.ring_teeth,
        addendum=geometry_key.addendum,
        dedendum=geometry_key.dedendum,
        pressure_angle=geometry_key.pressure_angle_radians,
        sample_count=sample_count,
    )
    return sun_outline, planet_outline, ring_inner_outline


@lru_cache(maxsize=128)
def _cached_circle(radius: float, sample_count: int) -> np.ndarray:
    return sample_circle_points((0.0, 0.0), radius, sample_count=sample_count)


@lru_cache(maxsize=128)
def _planet_phase_offsets(geometry_key: PlanetaryGeometryKey, effective_planet_count: int) -> tuple[float, ...]:
    sun_outline, planet_outline, ring_outline = _cached_local_outlines(geometry_key, DEFAULT_GEAR_SAMPLE_COUNT)
    sun_profile = _build_polar_profile(sun_outline)
    planet_profile = _build_polar_profile(planet_outline)
    ring_profile = _build_polar_profile(ring_outline)

    tooth_pitch = 2.0 * np.pi / max(geometry_key.planet_teeth, 1)
    base_angles = np.linspace(0.0, 2.0 * np.pi, effective_planet_count, endpoint=False)
    phase_offsets = []
    for base_angle in base_angles:
        phase_offset = _find_best_planet_phase_offset(
            geometry_key,
            sun_profile,
            planet_profile,
            ring_profile,
            float(base_angle),
        )
        phase_offsets.append(float(np.mod(phase_offset, tooth_pitch)))
    return tuple(phase_offsets)


def _find_best_planet_phase_offset(
    geometry_key: PlanetaryGeometryKey,
    sun_profile: tuple[np.ndarray, np.ndarray],
    planet_profile: tuple[np.ndarray, np.ndarray],
    ring_profile: tuple[np.ndarray, np.ndarray],
    base_angle: float,
) -> float:
    tooth_pitch = 2.0 * np.pi / max(geometry_key.planet_teeth, 1)
    phase_candidates = np.linspace(0.0, tooth_pitch, 720, endpoint=False)
    errors = [
        _planet_phase_error(geometry_key, sun_profile, planet_profile, ring_profile, base_angle, phase)
        for phase in phase_candidates
    ]
    coarse_best = float(phase_candidates[int(np.argmin(errors))])

    fine_span = tooth_pitch / 180.0
    fine_candidates = np.linspace(coarse_best - fine_span, coarse_best + fine_span, 240)
    fine_best = min(
        fine_candidates,
        key=lambda phase: _planet_phase_error(geometry_key, sun_profile, planet_profile, ring_profile, base_angle, phase),
    )
    return float(np.mod(fine_best, tooth_pitch))


def _planet_phase_error(
    geometry_key: PlanetaryGeometryKey,
    sun_profile: tuple[np.ndarray, np.ndarray],
    planet_profile: tuple[np.ndarray, np.ndarray],
    ring_profile: tuple[np.ndarray, np.ndarray],
    base_angle: float,
    phase_offset: float,
) -> float:
    tooth_pitch = 2.0 * np.pi / max(geometry_key.sun_teeth, 1)
    contact_offsets = np.linspace(-0.32 * tooth_pitch, 0.32 * tooth_pitch, 7)
    error = 0.0

    for contact_offset in contact_offsets:
        contact_angle = base_angle + contact_offset
        sun_radius = _radius_at_angle(sun_profile, contact_angle)
        planet_inward_radius = _radius_at_angle(planet_profile, contact_angle + np.pi - phase_offset)
        ring_radius = _radius_at_angle(ring_profile, contact_angle)
        planet_outward_radius = _radius_at_angle(planet_profile, contact_angle - phase_offset)

        sun_gap = geometry_key.carrier_radius - (sun_radius + planet_inward_radius)
        ring_gap = geometry_key.carrier_radius - (ring_radius - planet_outward_radius)
        error += sun_gap**2 + ring_gap**2

    return error


def _maximum_geometry_planet_count(geometry_key: PlanetaryGeometryKey) -> int:
    outer_planet_radius = geometry_key.planet_tip_radius
    if geometry_key.carrier_radius <= outer_planet_radius:
        return 2

    ratio = min(0.98, outer_planet_radius / geometry_key.carrier_radius)
    max_count = int(np.floor(np.pi / np.arcsin(ratio)))
    return max(2, min(max_count, 6))


def _build_external_gear_outline(
    pitch_radius: float,
    teeth: int,
    addendum: float,
    dedendum: float,
    pressure_angle: float,
    sample_count: int,
) -> np.ndarray:
    return _build_involute_gear_outline(
        pitch_radius=pitch_radius,
        teeth=teeth,
        addendum=addendum,
        dedendum=dedendum,
        pressure_angle=pressure_angle,
        sample_count=sample_count,
        ring=False,
    )


def _build_internal_ring_outline(
    pitch_radius: float,
    teeth: int,
    addendum: float,
    dedendum: float,
    pressure_angle: float,
    sample_count: int,
) -> np.ndarray:
    return _build_involute_gear_outline(
        pitch_radius=pitch_radius,
        teeth=teeth,
        addendum=addendum,
        dedendum=dedendum,
        pressure_angle=pressure_angle,
        sample_count=sample_count,
        ring=True,
    )


def _build_involute_gear_outline(
    pitch_radius: float,
    teeth: int,
    addendum: float,
    dedendum: float,
    pressure_angle: float,
    sample_count: int,
    ring: bool,
) -> np.ndarray:
    teeth = max(4, int(round(teeth)))
    working_addendum = dedendum if ring else addendum
    working_dedendum = addendum if ring else dedendum
    pitch_angle = 2.0 * np.pi / teeth
    base_radius = pitch_radius * np.cos(pressure_angle)
    outer_radius = pitch_radius + working_addendum
    root_radius = max(pitch_radius - working_dedendum, pitch_radius * 0.10, 0.1)
    angular_backlash = (DEFAULT_BACKLASH_FACTOR * max(addendum, 0.1)) / max(2.0 * pitch_radius, 0.1)
    tooth_angle = pitch_angle / 2.0 + (angular_backlash if ring else -angular_backlash)

    half_tooth = _build_half_tooth_profile(
        base_radius=base_radius,
        pitch_radius=pitch_radius,
        outer_radius=outer_radius,
        root_radius=root_radius,
        tooth_angle=tooth_angle,
        sample_count=sample_count,
    )
    mirrored_half = half_tooth.copy()
    mirrored_half[1] *= -1.0
    mirrored_half = np.flip(mirrored_half, axis=1)
    full_tooth = np.concatenate((half_tooth, mirrored_half), axis=1)
    full_tooth = _reduce_polyline(full_tooth, tolerance=max(0.003, 3.0 * np.pi / max(sample_count, 120)))

    half_root = _build_half_root_profile(
        root_radius=root_radius,
        pitch_angle=pitch_angle,
        full_tooth=full_tooth,
        sample_count=sample_count,
    )
    mirrored_root = half_root.copy()
    mirrored_root[1] *= -1.0
    mirrored_root = np.flip(mirrored_root, axis=1)
    tooth_and_gap = np.concatenate((mirrored_root, full_tooth, half_root), axis=1)

    repeated_segments = []
    for tooth_index in range(teeth):
        repeated_segments.append(_rotation_matrix(pitch_angle * tooth_index) @ tooth_and_gap)

    outline = np.concatenate(repeated_segments, axis=1).T
    return np.vstack((outline, outline[0]))


def _build_half_tooth_profile(
    base_radius: float,
    pitch_radius: float,
    outer_radius: float,
    root_radius: float,
    tooth_angle: float,
    sample_count: int,
) -> np.ndarray:
    point_budget = max(80, sample_count // 12)
    theta_pitch_intersect = None
    theta_full_tooth = None
    points = []

    for parameter in np.linspace(0.0, np.pi, point_budget):
        x_value = (base_radius * np.cos(parameter)) + (parameter * base_radius * np.sin(parameter))
        y_value = (base_radius * np.sin(parameter)) - (parameter * base_radius * np.cos(parameter))
        distance, theta = _cart_to_polar(x_value, y_value)

        if theta_pitch_intersect is None and distance >= pitch_radius:
            theta_pitch_intersect = theta
            theta_full_tooth = theta_pitch_intersect * 2.0 + tooth_angle
        elif theta_pitch_intersect is not None and theta >= theta_full_tooth / 2.0:
            break

        if distance >= outer_radius:
            points.append(_polar_to_cart(outer_radius, theta))
        elif distance <= root_radius:
            points.append(_polar_to_cart(root_radius, theta))
        else:
            points.append((x_value, y_value))

    if not points:
        raise RuntimeError("Unable to build involute tooth profile.")

    half_tooth = np.array(points, dtype=float).T
    theta_full_tooth = theta_full_tooth or tooth_angle
    return _rotation_matrix(-theta_full_tooth / 2.0) @ half_tooth


def _build_half_root_profile(
    root_radius: float,
    pitch_angle: float,
    full_tooth: np.ndarray,
    sample_count: int,
) -> np.ndarray:
    tooth_angles = np.arctan2(full_tooth[1], full_tooth[0])
    tooth_span = float(tooth_angles[-1] - tooth_angles[0])
    start_angle = tooth_span
    end_angle = pitch_angle / 2.0 + tooth_span / 2.0
    arc_samples = max(6, sample_count // 64)
    angles = np.linspace(start_angle, end_angle, arc_samples)
    root_points = np.array([_polar_to_cart(root_radius, angle) for angle in angles], dtype=float).T
    return _rotation_matrix(-tooth_span / 2.0) @ root_points


def _reduce_polyline(polyline: np.ndarray, tolerance: float) -> np.ndarray:
    vertices_x = [float(polyline[0, 0])]
    vertices_y = [float(polyline[1, 0])]
    last_x = float(polyline[0, 0])
    last_y = float(polyline[1, 0])

    for index in range(1, polyline.shape[1] - 1):
        next_slope = np.arctan2(polyline[1, index + 1] - polyline[1, index], polyline[0, index + 1] - polyline[0, index])
        previous_slope = np.arctan2(polyline[1, index] - last_y, polyline[0, index] - last_x)
        deviation_angle = abs(previous_slope - next_slope)

        if deviation_angle > tolerance:
            vertices_x.append(float(polyline[0, index]))
            vertices_y.append(float(polyline[1, index]))
            last_x = float(polyline[0, index])
            last_y = float(polyline[1, index])

    vertices_x.append(float(polyline[0, -1]))
    vertices_y.append(float(polyline[1, -1]))
    return np.array([vertices_x, vertices_y], dtype=float)


def transform_outline(points: np.ndarray, center: tuple[float, float] = (0.0, 0.0), rotation: float = 0.0) -> np.ndarray:
    rotated = _rotate_points(points, rotation)
    translated = rotated.copy()
    translated[:, 0] += center[0]
    translated[:, 1] += center[1]
    return translated


def _rotate_points(points: np.ndarray, angle: float) -> np.ndarray:
    cosine = np.cos(angle)
    sine = np.sin(angle)
    x_values = points[:, 0] * cosine - points[:, 1] * sine
    y_values = points[:, 0] * sine + points[:, 1] * cosine
    return np.column_stack((x_values, y_values))


def _rotation_matrix(angle: float) -> np.ndarray:
    return np.array(
        [
            [np.cos(angle), -np.sin(angle)],
            [np.sin(angle), np.cos(angle)],
        ],
        dtype=float,
    )


def _polar_to_cart(radius: float, angle: float) -> tuple[float, float]:
    return (float(radius * np.cos(angle)), float(radius * np.sin(angle)))


def _cart_to_polar(x_value: float, y_value: float) -> tuple[float, float]:
    return (float(np.hypot(x_value, y_value)), float(np.arctan2(y_value, x_value)))


def _involute_points(base_radius: float, parameters: np.ndarray) -> np.ndarray:
    cosine = np.cos(parameters)
    sine = np.sin(parameters)
    x_values = base_radius * (cosine + parameters * sine)
    y_values = base_radius * (sine - parameters * cosine)
    return np.column_stack((x_values, y_values))


def _involute_parameter_for_radius(base_radius: float, radius: float) -> float:
    if radius <= base_radius:
        return 0.0
    return float(np.sqrt((radius / base_radius) ** 2 - 1.0))


def _involute_polar_angle(base_radius: float, parameter: float) -> float:
    point = _involute_points(base_radius, np.array([parameter], dtype=float))[0]
    return float(np.arctan2(point[1], point[0]))


def _build_polar_profile(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    angles = np.unwrap(np.arctan2(points[:, 1], points[:, 0]))
    radii = np.hypot(points[:, 0], points[:, 1])
    if angles[-1] <= angles[0]:
        angles[-1] = angles[0] + 2.0 * np.pi
    return angles, radii


def _radius_at_angle(profile: tuple[np.ndarray, np.ndarray], angle: float) -> float:
    angles, radii = profile
    start_angle = angles[0]
    normalized_angle = start_angle + np.mod(angle - start_angle, 2.0 * np.pi)
    return float(np.interp(normalized_angle, angles, radii))


def _add_layers(document) -> None:
    layers = (
        ("ring_gear", 5),
        ("sun_gear", 1),
        ("planet_gears", 3),
        ("carrier", 8),
        ("bores", 7),
    )

    for name, color in layers:
        if name not in document.layers:
            document.layers.add(name, color=color)

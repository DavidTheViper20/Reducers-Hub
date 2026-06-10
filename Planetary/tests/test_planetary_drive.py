import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import ezdxf

from planetary_drive import (
    DEFAULT_MODE_KEY,
    DXF_UNITS_LABEL,
    MODE_LABEL,
    DEFAULT_GEAR_SAMPLE_COUNT,
    PlanetaryParameters,
    SUN_PHASE_TRIM,
    _build_polar_profile,
    _cached_local_outlines,
    _planet_phase_offsets,
    _planet_phase_error,
    _radius_at_angle,
    build_scene_geometry,
    effective_planet_count_for_parameters,
    export_scene_to_dxf,
    resolve_motion,
    reveal_in_finder,
)


class PlanetaryDriveTests(unittest.TestCase):
    def test_labels_expose_units_and_default_mode(self):
        self.assertIn("millimeters", DXF_UNITS_LABEL.lower())
        self.assertEqual(MODE_LABEL, "Operating mode: fixed ring, sun input, carrier output.")
        self.assertEqual(DEFAULT_MODE_KEY, "fixed_ring_sun_input")

    def test_ring_tooth_count_matches_sun_and_planets(self):
        params = PlanetaryParameters(
            animation_frames=60,
            module=2.0,
            sun_teeth=20,
            planet_teeth=12,
            planet_count=3,
            tooth_depth=2.6,
            sun_bore_radius=5.0,
            planet_bore_radius=3.0,
            pressure_angle_degrees=20.0,
        )

        self.assertEqual(params.ring_teeth, 44)
        self.assertAlmostEqual(params.reduction_ratio, 3.2)
        self.assertAlmostEqual(params.pressure_angle_radians, 0.3490658504, places=6)

    def test_scene_geometry_builds_all_requested_planets_when_they_fit(self):
        params = PlanetaryParameters(
            animation_frames=60,
            module=2.0,
            sun_teeth=18,
            planet_teeth=12,
            planet_count=3,
            tooth_depth=2.6,
            sun_bore_radius=5.0,
            planet_bore_radius=3.0,
            pressure_angle_degrees=20.0,
        )

        geometry = build_scene_geometry(params, input_angle=0.0)

        self.assertEqual(geometry.effective_planet_count, 3)
        self.assertEqual(len(geometry.planet_outlines), 3)
        self.assertEqual(len(geometry.carrier_arm_segments), 3)
        self.assertEqual(len(geometry.planet_bore_circles), 3)

    def test_effective_planet_count_prefers_the_nearest_compatible_layout(self):
        params = PlanetaryParameters(
            animation_frames=60,
            module=2.0,
            sun_teeth=20,
            planet_teeth=12,
            planet_count=3,
            tooth_depth=2.6,
            sun_bore_radius=5.0,
            planet_bore_radius=3.0,
            pressure_angle_degrees=20.0,
        )

        self.assertEqual(effective_planet_count_for_parameters(params), 4)

    def test_resolve_motion_for_fixed_carrier_mode_keeps_planet_centers_stationary(self):
        params = PlanetaryParameters(
            animation_frames=60,
            module=2.0,
            sun_teeth=18,
            planet_teeth=12,
            planet_count=3,
            tooth_depth=2.6,
            sun_bore_radius=5.0,
            planet_bore_radius=3.0,
            pressure_angle_degrees=20.0,
        )

        motion = resolve_motion(params, "fixed_carrier_ring_input", input_angle=1.25)
        initial_geometry = build_scene_geometry(params, input_angle=0.0, mode_key="fixed_carrier_ring_input")
        later_geometry = build_scene_geometry(params, input_angle=1.25, mode_key="fixed_carrier_ring_input")

        self.assertAlmostEqual(motion.carrier_angle, 0.0)
        self.assertLess(motion.sun_angle, 0.0)
        self.assertEqual(initial_geometry.planet_centers, later_geometry.planet_centers)

    def test_resolve_motion_for_fixed_sun_mode_keeps_sun_locked(self):
        params = PlanetaryParameters(
            animation_frames=60,
            module=2.0,
            sun_teeth=18,
            planet_teeth=12,
            planet_count=3,
            tooth_depth=2.6,
            sun_bore_radius=5.0,
            planet_bore_radius=3.0,
            pressure_angle_degrees=20.0,
        )

        motion = resolve_motion(params, "fixed_sun_ring_input", input_angle=1.1)

        self.assertAlmostEqual(motion.sun_angle, 0.0)
        self.assertGreater(motion.ring_angle, 0.0)
        self.assertGreater(motion.carrier_angle, 0.0)

    def test_sun_phase_trim_keeps_the_default_mesh_baseline(self):
        params = PlanetaryParameters(
            animation_frames=60,
            module=2.0,
            sun_teeth=18,
            planet_teeth=12,
            planet_count=3,
            tooth_depth=2.6,
            sun_bore_radius=5.0,
            planet_bore_radius=3.0,
            pressure_angle_degrees=20.0,
        )
        geometry_key = params.geometry_key
        sun_outline, planet_outline, _ring_outline = _cached_local_outlines(geometry_key, DEFAULT_GEAR_SAMPLE_COUNT)
        sun_profile = _build_polar_profile(sun_outline)
        planet_profile = _build_polar_profile(planet_outline)
        phase_offset = _planet_phase_offsets(geometry_key, 3)[0]
        tooth_pitch = 2.0 * 3.141592653589793 / geometry_key.sun_teeth

        def sun_mesh_error(sun_shift: float) -> float:
            total = 0.0
            for base_angle in (0.0, 2.0 * 3.141592653589793 / 3.0, 4.0 * 3.141592653589793 / 3.0):
                for contact_offset in (-0.32 * tooth_pitch, -0.16 * tooth_pitch, 0.0, 0.16 * tooth_pitch, 0.32 * tooth_pitch):
                    contact_angle = base_angle + contact_offset
                    sun_radius = _radius_at_angle(sun_profile, contact_angle - sun_shift)
                    planet_radius = _radius_at_angle(planet_profile, contact_angle + 3.141592653589793 - phase_offset)
                    gap = geometry_key.carrier_radius - (sun_radius + planet_radius)
                    total += gap**2
            return total

        self.assertEqual(SUN_PHASE_TRIM, 0.0)
        self.assertLessEqual(sun_mesh_error(SUN_PHASE_TRIM), sun_mesh_error(0.0))

    def test_phase_offsets_reduce_mesh_error_for_each_planet_position(self):
        params = PlanetaryParameters(
            animation_frames=60,
            module=2.0,
            sun_teeth=18,
            planet_teeth=12,
            planet_count=5,
            tooth_depth=2.6,
            sun_bore_radius=5.0,
            planet_bore_radius=3.0,
            pressure_angle_degrees=20.0,
        )

        geometry_key = params.geometry_key
        sun_outline, planet_outline, ring_outline = _cached_local_outlines(geometry_key, DEFAULT_GEAR_SAMPLE_COUNT)
        sun_profile = _build_polar_profile(sun_outline)
        planet_profile = _build_polar_profile(planet_outline)
        ring_profile = _build_polar_profile(ring_outline)
        effective_count = effective_planet_count_for_parameters(params)
        offsets = _planet_phase_offsets(geometry_key, effective_count)
        base_angles = [index * 2.0 * 3.141592653589793 / effective_count for index in range(effective_count)]

        self.assertEqual(len(offsets), effective_count)
        self.assertGreater(len({round(offset, 6) for offset in offsets}), 1)

        for base_angle, offset in zip(base_angles, offsets):
            self.assertLess(
                _planet_phase_error(geometry_key, sun_profile, planet_profile, ring_profile, base_angle, offset),
                _planet_phase_error(geometry_key, sun_profile, planet_profile, ring_profile, base_angle, 0.0),
            )

    def test_export_scene_to_dxf_omits_carrier_arm_segments(self):
        params = PlanetaryParameters(
            animation_frames=60,
            module=2.0,
            sun_teeth=18,
            planet_teeth=12,
            planet_count=3,
            tooth_depth=2.6,
            sun_bore_radius=5.0,
            planet_bore_radius=3.0,
            pressure_angle_degrees=20.0,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = export_scene_to_dxf(
                params,
                input_angle=0.0,
                output_dir=Path(temp_dir),
                exported_at=datetime(2026, 5, 27, 9, 40, 0),
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.name, "planetary-fixed-ring-20260527-094000.dxf")

            document = ezdxf.readfile(output_path)
            entities = list(document.modelspace())
            circles = [entity for entity in entities if entity.dxftype() == "CIRCLE"]
            polylines = [entity for entity in entities if entity.dxftype() == "LWPOLYLINE"]

            self.assertEqual(len(circles), 4)
            self.assertGreaterEqual(len(polylines), 7)
            self.assertFalse(any(len(entity.get_points()) == 2 for entity in polylines))

    def test_export_scene_to_dxf_honors_bore_toggles(self):
        params = PlanetaryParameters(
            animation_frames=60,
            module=2.0,
            sun_teeth=18,
            planet_teeth=12,
            planet_count=3,
            tooth_depth=2.6,
            sun_bore_radius=5.0,
            planet_bore_radius=3.0,
            pressure_angle_degrees=20.0,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = export_scene_to_dxf(
                params,
                input_angle=0.0,
                output_dir=Path(temp_dir),
                exported_at=datetime(2026, 5, 27, 9, 41, 0),
                include_sun_bore=False,
                include_planet_bores=False,
            )

            document = ezdxf.readfile(output_path)
            entities = list(document.modelspace())
            circles = [entity for entity in entities if entity.dxftype() == "CIRCLE"]

            self.assertEqual(circles, [])

    def test_export_scene_to_dxf_uses_custom_name_when_provided(self):
        params = PlanetaryParameters(
            animation_frames=60,
            module=2.0,
            sun_teeth=18,
            planet_teeth=12,
            planet_count=3,
            tooth_depth=2.6,
            sun_bore_radius=5.0,
            planet_bore_radius=3.0,
            pressure_angle_degrees=20.0,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = export_scene_to_dxf(
                params,
                input_angle=0.0,
                output_dir=Path(temp_dir),
                file_name="fixed-ring-customer-export",
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.name, "fixed-ring-customer-export.dxf")

    def test_reveal_in_finder_uses_open_reveal(self):
        captured = {}

        def fake_runner(command, check):
            captured["command"] = command
            captured["check"] = check
            return SimpleNamespace(returncode=0)

        target_path = Path("/tmp/planetary-example.dxf")
        reveal_in_finder(target_path, runner=fake_runner)

        self.assertEqual(captured["command"], ["open", "-R", str(target_path)])
        self.assertTrue(captured["check"])


if __name__ == "__main__":
    unittest.main()

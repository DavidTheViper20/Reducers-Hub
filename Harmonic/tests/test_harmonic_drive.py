import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import numpy as np

from harmonic_drive import (
    DXF_UNITS_LABEL,
    HarmonicParameters,
    build_scene_geometry,
    export_scene_to_dxf,
    reveal_in_finder,
)


class HarmonicDriveTests(unittest.TestCase):
    def test_labels_and_ratio_match_fixed_circular_mode(self):
        self.assertIn("millimeters", DXF_UNITS_LABEL.lower())
        params = HarmonicParameters(
            animation_frames=72,
            module=1.2,
            flex_teeth=40,
            circular_teeth=42,
            tooth_depth=1.0,
            wave_generator_thickness=1.6,
            bore_radius=6.0,
            pressure_angle_degrees=20.0,
        )

        self.assertAlmostEqual(params.reduction_ratio, 20.0)
        self.assertEqual(params.tooth_difference, 2)
        self.assertGreater(params.wave_amplitude, 0.0)

    def test_scene_geometry_builds_wave_generator_and_flex_spline(self):
        params = HarmonicParameters(
            animation_frames=72,
            module=1.2,
            flex_teeth=40,
            circular_teeth=42,
            tooth_depth=1.0,
            wave_generator_thickness=1.6,
            bore_radius=6.0,
            pressure_angle_degrees=20.0,
        )

        geometry = build_scene_geometry(params, input_angle=0.0)

        self.assertGreater(len(geometry.circular_spline_outline), 1000)
        self.assertGreater(len(geometry.flex_spline_outline), 1000)
        self.assertGreater(len(geometry.circular_body_outline), 200)
        self.assertGreater(len(geometry.flex_inner_outline), 200)
        self.assertGreater(len(geometry.wave_generator_inner_outline), 200)
        self.assertGreater(len(geometry.wave_generator_outline), 200)

    def test_export_scene_to_dxf_writes_three_primary_profiles(self):
        params = HarmonicParameters(
            animation_frames=72,
            module=1.2,
            flex_teeth=40,
            circular_teeth=42,
            tooth_depth=1.0,
            wave_generator_thickness=1.6,
            bore_radius=6.0,
            pressure_angle_degrees=20.0,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = export_scene_to_dxf(
                params,
                input_angle=0.0,
                output_dir=Path(temp_dir),
                exported_at=datetime(2026, 5, 27, 22, 45, 0),
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.name, "harmonic-drive-20260527-224500.dxf")

            document = ezdxf.readfile(output_path)
            polylines = [entity for entity in document.modelspace() if entity.dxftype() == "LWPOLYLINE"]
            circles = [entity for entity in document.modelspace() if entity.dxftype() == "CIRCLE"]

            self.assertGreaterEqual(len(polylines), 3)
            self.assertGreaterEqual(len(circles), 1)

    def test_pressure_angle_changes_tooth_profile_and_wave_compression_shortens_minor_axis(self):
        low_angle = HarmonicParameters(
            animation_frames=72,
            module=1.2,
            flex_teeth=40,
            circular_teeth=42,
            tooth_depth=1.0,
            wave_generator_thickness=1.0,
            bore_radius=6.0,
            pressure_angle_degrees=14.0,
        )
        high_angle = HarmonicParameters(
            animation_frames=72,
            module=1.2,
            flex_teeth=40,
            circular_teeth=42,
            tooth_depth=1.0,
            wave_generator_thickness=1.0,
            bore_radius=6.0,
            pressure_angle_degrees=28.0,
        )
        compressed_generator = HarmonicParameters(
            animation_frames=72,
            module=1.2,
            flex_teeth=40,
            circular_teeth=42,
            tooth_depth=1.0,
            wave_generator_thickness=3.0,
            bore_radius=6.0,
            pressure_angle_degrees=20.0,
        )

        low_geometry = build_scene_geometry(low_angle, input_angle=0.0)
        high_geometry = build_scene_geometry(high_angle, input_angle=0.0)

        self.assertNotEqual(
            low_geometry.circular_spline_outline[:20].round(4).tolist(),
            high_geometry.circular_spline_outline[:20].round(4).tolist(),
        )
        self.assertAlmostEqual(
            compressed_generator.wave_generator_outer_major_axis,
            low_angle.wave_generator_outer_major_axis,
            delta=0.25,
        )
        self.assertLess(
            compressed_generator.wave_generator_outer_minor_axis,
            low_angle.wave_generator_outer_minor_axis - 0.9,
        )

    def test_flex_spline_reaches_ring_contact_at_wave_peaks(self):
        params = HarmonicParameters(
            animation_frames=72,
            module=1.2,
            flex_teeth=40,
            circular_teeth=42,
            tooth_depth=1.0,
            wave_generator_thickness=1.6,
            bore_radius=6.0,
            pressure_angle_degrees=20.0,
        )

        geometry = build_scene_geometry(params, input_angle=0.0)
        ring_radii = np.hypot(geometry.circular_spline_outline[:, 0], geometry.circular_spline_outline[:, 1])
        flex_radii = np.hypot(geometry.flex_spline_outline[:, 0], geometry.flex_spline_outline[:, 1])
        max_flex_index = int(np.argmax(flex_radii))

        self.assertLess(ring_radii[max_flex_index] - flex_radii[max_flex_index], 0.45)

    def test_default_contact_gap_stays_tight_at_wave_lobes(self):
        params = HarmonicParameters(
            animation_frames=72,
            module=1.2,
            flex_teeth=40,
            circular_teeth=42,
            tooth_depth=1.0,
            wave_generator_thickness=0.9,
            bore_radius=6.0,
            pressure_angle_degrees=20.0,
        )

        geometry = build_scene_geometry(params, input_angle=0.0)
        ring_radii = np.hypot(geometry.circular_spline_outline[:, 0], geometry.circular_spline_outline[:, 1])
        flex_radii = np.hypot(geometry.flex_spline_outline[:, 0], geometry.flex_spline_outline[:, 1])
        contact_angles = np.arctan2(geometry.flex_spline_outline[:, 1], geometry.flex_spline_outline[:, 0])

        for target_angle in (0.0, np.pi):
            index = int(np.argmin(np.abs(np.unwrap(contact_angles - target_angle))))
            self.assertLess(ring_radii[index] - flex_radii[index], 0.32)

    def test_export_scene_to_dxf_uses_custom_name_when_provided(self):
        params = HarmonicParameters(
            animation_frames=72,
            module=1.2,
            flex_teeth=40,
            circular_teeth=42,
            tooth_depth=1.0,
            wave_generator_thickness=1.6,
            bore_radius=6.0,
            pressure_angle_degrees=20.0,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = export_scene_to_dxf(
                params,
                input_angle=0.0,
                output_dir=Path(temp_dir),
                file_name="harmonic-customer-export",
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.name, "harmonic-customer-export.dxf")

    def test_reveal_in_finder_uses_open_reveal(self):
        captured = {}

        def fake_runner(command, check):
            captured["command"] = command
            captured["check"] = check
            return SimpleNamespace(returncode=0)

        target_path = Path("/tmp/harmonic-drive-example.dxf")
        reveal_in_finder(target_path, runner=fake_runner)

        self.assertEqual(captured["command"], ["open", "-R", str(target_path)])
        self.assertTrue(captured["check"])


if __name__ == "__main__":
    unittest.main()

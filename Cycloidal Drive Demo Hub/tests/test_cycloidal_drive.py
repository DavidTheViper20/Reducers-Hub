import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import ezdxf

from cycloidal_drive import DXF_UNITS_LABEL, DriveParameters, build_scene_geometry, export_scene_to_dxf, reveal_in_finder


class CycloidalDriveExportTests(unittest.TestCase):
    def test_dxf_units_label_mentions_millimeters(self):
        self.assertIn("millimeters", DXF_UNITS_LABEL.lower())
        self.assertIn("(mm)", DXF_UNITS_LABEL)

    def test_scene_geometry_matches_parameterized_pin_count(self):
        params = DriveParameters(
            animation_frames=50,
            center_circle_radius=20,
            drive_pin_radius=1.5,
            eccentricity=2.0,
            pin_count=17,
            outer_pin_diameter=10,
            pin_circle_diameter=80,
        )

        geometry = build_scene_geometry(params, phi=0.0)

        self.assertEqual(len(geometry.outer_pin_centers), 17)
        self.assertEqual(len(geometry.drive_pin_centers), 17)
        self.assertEqual(geometry.outer_pin_radius, 5.0)
        self.assertEqual(geometry.drive_pin_radius, 1.5)
        self.assertEqual(len(geometry.hypocycloid_a), 2000)
        self.assertEqual(len(geometry.hypocycloid_b), 2000)

    def test_export_scene_to_dxf_writes_circles_and_curves(self):
        params = DriveParameters(
            animation_frames=50,
            center_circle_radius=20,
            drive_pin_radius=1.5,
            eccentricity=2.0,
            pin_count=17,
            outer_pin_diameter=10,
            pin_circle_diameter=80,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = export_scene_to_dxf(
                params,
                phi=0.0,
                output_dir=Path(temp_dir),
                exported_at=datetime(2026, 5, 26, 19, 20, 11),
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.name, "cycloidal-drive-20260526-192011.dxf")

            document = ezdxf.readfile(output_path)
            entities = list(document.modelspace())
            circles = [entity for entity in entities if entity.dxftype() == "CIRCLE"]
            polylines = [entity for entity in entities if entity.dxftype() == "LWPOLYLINE"]

            self.assertEqual(len(circles), 35)
            self.assertEqual(len(polylines), 2)

    def test_export_scene_to_dxf_uses_custom_name_when_provided(self):
        params = DriveParameters(
            animation_frames=50,
            center_circle_radius=20,
            drive_pin_radius=1.5,
            eccentricity=2.0,
            pin_count=17,
            outer_pin_diameter=10,
            pin_circle_diameter=80,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = export_scene_to_dxf(
                params,
                phi=0.0,
                output_dir=Path(temp_dir),
                file_name="customer-ring-profile",
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.name, "customer-ring-profile.dxf")

    def test_reveal_in_finder_uses_open_reveal(self):
        captured = {}

        def fake_runner(command, check):
            captured["command"] = command
            captured["check"] = check
            return SimpleNamespace(returncode=0)

        target_path = Path("/tmp/example.dxf")
        reveal_in_finder(target_path, runner=fake_runner)

        self.assertEqual(captured["command"], ["open", "-R", str(target_path)])
        self.assertTrue(captured["check"])


if __name__ == "__main__":
    unittest.main()

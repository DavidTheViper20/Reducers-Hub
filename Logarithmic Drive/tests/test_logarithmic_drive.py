import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import numpy as np

from logarithmic_drive import (
    DXF_UNITS_LABEL,
    LogarithmicParameters,
    build_scene_geometry,
    export_scene_to_dxf,
    export_split_scene_to_dxf,
    reveal_in_finder,
)


class LogarithmicDriveTests(unittest.TestCase):
    def test_labels_and_ratios_match_novel_drive_defaults(self):
        self.assertIn("millimeters", DXF_UNITS_LABEL.lower())
        params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
        )

        self.assertEqual(params.ball_count, 12)
        self.assertAlmostEqual(params.reduction_ratio, 13.0)
        self.assertAlmostEqual(params.input_track_short_axis_width, 50.0)

    def test_scene_geometry_builds_matching_ball_and_hole_sets(self):
        params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
        )

        geometry = build_scene_geometry(params, input_angle=0.0)

        self.assertEqual(len(geometry.hole_centers), params.ball_count)
        self.assertEqual(len(geometry.slot_outlines), params.ball_count)
        self.assertEqual(len(geometry.ball_centers), params.ball_count)
        self.assertGreater(len(geometry.ellipse_outline), 1000)
        self.assertGreater(len(geometry.hypocycloid_outline), 1000)
        self.assertGreater(len(geometry.output_trochoid_outline), 1000)
        self.assertFalse(hasattr(geometry, "output_inner_outline"))
        self.assertFalse(hasattr(geometry, "output_outer_outline"))

    def test_ball_stations_keep_fixed_angles_while_radii_breathe(self):
        params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
        )

        geometry_a = build_scene_geometry(params, input_angle=0.0)
        geometry_b = build_scene_geometry(params, input_angle=0.7)

        angles_a = [round(float(__import__("math").atan2(y_value, x_value)), 6) for x_value, y_value in geometry_a.ball_centers]
        angles_b = [round(float(__import__("math").atan2(y_value, x_value)), 6) for x_value, y_value in geometry_b.ball_centers]
        radii_a = [round(float((x_value**2 + y_value**2) ** 0.5), 6) for x_value, y_value in geometry_a.ball_centers]
        radii_b = [round(float((x_value**2 + y_value**2) ** 0.5), 6) for x_value, y_value in geometry_b.ball_centers]

        self.assertEqual(angles_a, angles_b)
        self.assertNotEqual(radii_a, radii_b)
        self.assertEqual(geometry_a.hole_centers, geometry_b.hole_centers)
        self.assertNotEqual(
            geometry_a.output_trochoid_outline[:10].tolist(),
            geometry_b.output_trochoid_outline[:10].tolist(),
        )

    def test_input_track_size_and_short_width_are_independent(self):
        narrow_params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
            input_track_short_width=34.0,
        )
        rounder_params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
            input_track_short_width=54.0,
        )

        narrow_geometry = build_scene_geometry(narrow_params, input_angle=0.0)
        rounder_geometry = build_scene_geometry(rounder_params, input_angle=0.0)
        narrow_x_radius = float(np.max(np.abs(narrow_geometry.ellipse_outline[:, 0])))
        rounder_x_radius = float(np.max(np.abs(rounder_geometry.ellipse_outline[:, 0])))
        narrow_y_radius = float(np.max(np.abs(narrow_geometry.ellipse_outline[:, 1])))
        rounder_y_radius = float(np.max(np.abs(rounder_geometry.ellipse_outline[:, 1])))

        self.assertAlmostEqual(narrow_x_radius, rounder_x_radius, places=6)
        self.assertLess(narrow_y_radius, rounder_y_radius)
        self.assertAlmostEqual(narrow_params.input_track_short_axis_width, 34.0)
        self.assertAlmostEqual(rounder_params.input_track_short_axis_width, 54.0)
        self.assertFalse(np.allclose(narrow_geometry.output_trochoid_outline, rounder_geometry.output_trochoid_outline))

    def test_output_profile_is_visible_and_distinct_from_ball_center_guide(self):
        params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
        )

        geometry = build_scene_geometry(params, input_angle=0.0)
        output_radii = np.hypot(geometry.output_trochoid_outline[:, 0], geometry.output_trochoid_outline[:, 1])
        guide_radii = np.hypot(geometry.hypocycloid_outline[:, 0], geometry.hypocycloid_outline[:, 1])
        common_count = min(len(output_radii), len(guide_radii))

        self.assertFalse(np.allclose(output_radii[:common_count], guide_radii[:common_count]))
        self.assertGreater(float(np.max(output_radii) - np.min(output_radii)), 1.5)
        self.assertGreater(float(np.max(np.abs(output_radii[:common_count] - guide_radii[:common_count]))), 1.0)

    def test_output_shape_is_rigid_reduced_output_body(self):
        params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
        )
        input_angle = 0.7

        starting_geometry = build_scene_geometry(params, input_angle=0.0)
        moved_geometry = build_scene_geometry(params, input_angle=input_angle)
        expected_output_angle = input_angle / params.reduction_ratio
        cosine = np.cos(expected_output_angle)
        sine = np.sin(expected_output_angle)
        expected_output = np.column_stack(
            (
                starting_geometry.output_trochoid_outline[:, 0] * cosine
                - starting_geometry.output_trochoid_outline[:, 1] * sine,
                starting_geometry.output_trochoid_outline[:, 0] * sine
                + starting_geometry.output_trochoid_outline[:, 1] * cosine,
            )
        )

        self.assertTrue(np.allclose(moved_geometry.output_trochoid_outline, expected_output))

    def test_output_track_stays_on_reduced_ball_set_across_motion(self):
        params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
        )

        maximum_clearances = []
        for input_angle in (0.0, 0.4, 1.0, 2.0):
            geometry = build_scene_geometry(params, input_angle=input_angle)
            curve = geometry.output_trochoid_outline[:-1]
            clearances = [
                float(np.min(np.hypot(curve[:, 0] - center_x, curve[:, 1] - center_y)))
                for center_x, center_y in geometry.ball_centers
            ]
            maximum_clearances.append(max(clearances))

        self.assertLess(max(maximum_clearances), 0.08)

    def test_output_track_matches_default_starting_sketch_ball_centers(self):
        params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
        )

        geometry = build_scene_geometry(params, input_angle=0.0)
        curve = geometry.output_trochoid_outline[:-1]
        clearances = [
            float(np.min(np.hypot(curve[:, 0] - center_x, curve[:, 1] - center_y)))
            for center_x, center_y in geometry.ball_centers
        ]

        self.assertLess(max(clearances), 0.08)

    def test_even_cusp_counts_keep_output_mesh_accurate(self):
        for cusp_count in (18, 22, 26, 30, 34):
            params = LogarithmicParameters(
                animation_frames=72,
                cusp_count=cusp_count,
                minor_axis_radius=25.0,
                ball_radius=2.5,
                clearance=0.0,
                show_every_other=False,
            )

            for input_angle in (0.0, 0.55, 1.1):
                with self.subTest(cusp_count=cusp_count, input_angle=input_angle):
                    geometry = build_scene_geometry(params, input_angle=input_angle)
                    curve = geometry.output_trochoid_outline[:-1]
                    clearances = [
                        float(np.min(np.hypot(curve[:, 0] - center_x, curve[:, 1] - center_y)))
                        for center_x, center_y in geometry.ball_centers
                    ]

                    self.assertLess(max(clearances), 0.10)

    def test_short_width_changes_keep_output_mesh_accurate(self):
        for short_width in (34.0, 44.0, 50.0, 54.0):
            params = LogarithmicParameters(
                animation_frames=72,
                cusp_count=26,
                minor_axis_radius=25.0,
                ball_radius=2.5,
                clearance=0.0,
                show_every_other=False,
                input_track_short_width=short_width,
            )

            for input_angle in (0.0, 0.7, 1.4):
                with self.subTest(short_width=short_width, input_angle=input_angle):
                    geometry = build_scene_geometry(params, input_angle=input_angle)
                    curve = geometry.output_trochoid_outline[:-1]
                    clearances = [
                        float(np.min(np.hypot(curve[:, 0] - center_x, curve[:, 1] - center_y)))
                        for center_x, center_y in geometry.ball_centers
                    ]

                    self.assertLess(max(clearances), 0.10)

    def test_export_scene_to_dxf_writes_curves_and_circles(self):
        params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = export_scene_to_dxf(
                params,
                input_angle=0.0,
                output_dir=Path(temp_dir),
                exported_at=datetime(2026, 5, 27, 22, 30, 0),
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.name, "logarithmic-drive-20260527-223000.dxf")

            document = ezdxf.readfile(output_path)
            entities = list(document.modelspace())
            circles = [entity for entity in entities if entity.dxftype() == "CIRCLE"]
            polylines = [entity for entity in entities if entity.dxftype() == "LWPOLYLINE"]

            self.assertGreaterEqual(len(circles), params.ball_count)
            self.assertGreaterEqual(len(polylines), params.ball_count + 3)

    def test_export_scene_to_dxf_uses_custom_name_when_provided(self):
        params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = export_scene_to_dxf(
                params,
                input_angle=0.0,
                output_dir=Path(temp_dir),
                file_name="novel-drive-input",
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.name, "novel-drive-input.dxf")

    def test_export_split_scene_to_dxf_writes_named_input_and_output_files(self):
        params = LogarithmicParameters(
            animation_frames=72,
            cusp_count=26,
            minor_axis_radius=25.0,
            ball_radius=2.5,
            clearance=0.0,
            show_every_other=False,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path, output_path = export_split_scene_to_dxf(
                params,
                input_angle=0.0,
                output_dir=Path(temp_dir),
                input_file_name="novel-input-and-balls",
                output_file_name="novel-output-shape",
            )

            self.assertTrue(input_path.exists())
            self.assertTrue(output_path.exists())
            self.assertEqual(input_path.name, "novel-input-and-balls.dxf")
            self.assertEqual(output_path.name, "novel-output-shape.dxf")

            input_document = ezdxf.readfile(input_path)
            input_entities = list(input_document.modelspace())
            input_circles = [entity for entity in input_entities if entity.dxftype() == "CIRCLE"]
            input_polylines = [entity for entity in input_entities if entity.dxftype() == "LWPOLYLINE"]

            output_document = ezdxf.readfile(output_path)
            output_entities = list(output_document.modelspace())
            output_circles = [entity for entity in output_entities if entity.dxftype() == "CIRCLE"]
            output_polylines = [entity for entity in output_entities if entity.dxftype() == "LWPOLYLINE"]

            self.assertGreaterEqual(len(input_circles), params.ball_count)
            self.assertEqual(len(output_circles), 0)
            self.assertGreaterEqual(len(input_polylines), params.ball_count + 1)
            self.assertEqual(len(output_polylines), 1)

    def test_reveal_in_finder_uses_open_reveal(self):
        captured = {}

        def fake_runner(command, check):
            captured["command"] = command
            captured["check"] = check
            return SimpleNamespace(returncode=0)

        target_path = Path("/tmp/logarithmic-drive-example.dxf")
        reveal_in_finder(target_path, runner=fake_runner)

        self.assertEqual(captured["command"], ["open", "-R", str(target_path)])
        self.assertTrue(captured["check"])


if __name__ == "__main__":
    unittest.main()

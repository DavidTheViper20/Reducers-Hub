import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from types import SimpleNamespace
from matplotlib.widgets import Button, Slider

from demo_hub import (
    DemoEntry,
    decorate_demo_window,
    discover_demo_entries,
    export_plot_axes_to_dxf,
    friendly_slider_label,
    prepare_demo_for_export,
    select_primary_axes,
)


class DemoHubTests(unittest.TestCase):
    def setUp(self):
        self.repo_dir = Path(__file__).resolve().parents[1]

    def test_discover_demo_entries_includes_original_demos(self):
        entries = discover_demo_entries(self.repo_dir)
        file_names = {entry.path.name for entry in entries}

        self.assertIn("demo_14.py", file_names)
        self.assertIn("demo_UI_ver1.py", file_names)
        self.assertIn("Animation for how dual stage cycloidal gearbox works.py", file_names)
        self.assertNotIn("demo_hub.py", file_names)
        self.assertNotIn("demo1_new.py", file_names)
        self.assertNotIn("demo_output_equition.py", file_names)

    def test_discover_demo_entries_returns_friendly_titles(self):
        entries = discover_demo_entries(self.repo_dir)
        demo_14 = next(entry for entry in entries if entry.path.name == "demo_14.py")

        self.assertIsInstance(demo_14, DemoEntry)
        self.assertEqual(demo_14.title, "Cycloidal Ring Explorer")
        self.assertIn("reference screenshot", demo_14.description.lower())

    def test_friendly_slider_label_expands_common_abbreviations(self):
        self.assertEqual(friendly_slider_label("fm"), "Animation Frames")
        self.assertEqual(friendly_slider_label("Rd"), "Center Circle Radius")
        self.assertEqual(friendly_slider_label("D2"), "Secondary Pin Circle Diameter")
        self.assertEqual(friendly_slider_label("unknown"), "unknown")

    def test_export_plot_axes_to_dxf_writes_visible_lines(self):
        figure, axis = plt.subplots()
        axis.plot([0, 10, 10, 0, 0], [0, 0, 10, 10, 0], color="red")
        axis.plot([2, 4, 6], [1, 3, 1], color="blue")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = export_plot_axes_to_dxf(
                axis,
                file_stem="demo-14",
                output_dir=Path(temp_dir),
                exported_at=datetime(2026, 5, 26, 20, 0, 0),
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.name, "demo-14-20260526-200000.dxf")

            document = ezdxf.readfile(output_path)
            polylines = [entity for entity in document.modelspace() if entity.dxftype() == "LWPOLYLINE"]
            self.assertEqual(len(polylines), 2)

        plt.close(figure)

    def test_export_plot_axes_to_dxf_uses_custom_name_when_provided(self):
        figure, axis = plt.subplots()
        axis.plot([0, 10, 10, 0, 0], [0, 0, 10, 10, 0], color="red")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = export_plot_axes_to_dxf(
                axis,
                file_stem="demo-14",
                output_dir=Path(temp_dir),
                file_name="wrapped-demo-export",
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.name, "wrapped-demo-export.dxf")

        plt.close(figure)

    def test_prepare_demo_for_export_prefers_initial_frame(self):
        calls = []
        draw_calls = []

        module = SimpleNamespace(
            animate=lambda frame: calls.append(("animate", frame)),
            figure=SimpleNamespace(canvas=SimpleNamespace(draw_idle=lambda: draw_calls.append("draw_idle"))),
        )

        prepare_demo_for_export(module)

        self.assertEqual(calls, [("animate", 0)])
        self.assertEqual(draw_calls, ["draw_idle"])

    def test_decorate_demo_window_keeps_buttons_alive_and_separates_controls(self):
        figure, axis = plt.subplots()
        axis.plot([0, 1, 2], [0, 1, 0], color="red")
        reset_axis = figure.add_axes([0.82, 0.08, 0.14, 0.04])
        reset_button = Button(reset_axis, "Reset")
        slider_axis = figure.add_axes([0.25, 0.30, 0.50, 0.02])
        frame_slider = Slider(slider_axis, "fm", 10, 100, valinit=50, valstep=1)
        module = SimpleNamespace(
            figure=figure,
            animate=lambda frame: None,
            reset_button=reset_button,
            frame_slider=frame_slider,
        )
        entry = DemoEntry(
            identifier="demo_1",
            title="Single-Stage Base Drive",
            description="Classic one-disc cycloidal drive.",
            path=self.repo_dir / "demo_1.py",
        )

        decorate_demo_window(module, entry)

        controls = module._cycloidal_hub_controls
        self.assertEqual(controls["open_location_button"].label.get_text(), "Open\nFiles")
        self.assertIs(getattr(figure, "_cycloidal_hub_controls"), controls)
        self.assertIs(getattr(controls["open_location_axis"], "_button"), controls["open_location_button"])

        slider_top = max(
            value.ax.get_position().y1
            for value in vars(module).values()
            if isinstance(value, Slider)
        )
        plot_bottom = axis.get_position().y0
        self.assertGreater(plot_bottom - slider_top, 0.12)

        plt.close(figure)

    def test_wrapped_export_handler_updates_last_export_path(self):
        figure, axis = plt.subplots()
        axis.plot([0, 1, 2], [0, 1, 0], color="red")
        reset_axis = figure.add_axes([0.82, 0.08, 0.14, 0.04])
        reset_button = Button(reset_axis, "Reset")
        module = SimpleNamespace(
            figure=figure,
            animate=lambda frame: None,
            reset_button=reset_button,
        )
        entry = DemoEntry(
            identifier="demo_4",
            title="Main and Counter Profile Pair",
            description="Shows a primary branch and a counter-rotated companion branch.",
            path=self.repo_dir / "demo_4.py",
        )

        decorate_demo_window(module, entry)
        expected_path = Path("/tmp/cycloidal-demo-test.dxf")
        with (
            patch("demo_hub.prompt_single_export_name", return_value="wrapped-demo-export"),
            patch("demo_hub.export_plot_axes_to_dxf", return_value=expected_path),
        ):
            module._cycloidal_hub_controls["handle_export"](None)

        self.assertEqual(module._cycloidal_hub_controls["state"]["last_export_path"], expected_path)
        self.assertIn("starting pose", module._cycloidal_hub_controls["status_text"].get_text())

        plt.close(figure)

    def test_select_primary_axes_prefers_large_plot_over_slider_axes(self):
        figure, axis = plt.subplots()
        axis.plot([0, 1, 2], [0, 1, 0], color="red")
        slider_axis = figure.add_axes([0.25, 0.10, 0.50, 0.015])
        slider_axis.plot([0, 1], [0.5, 0.5], color="blue")

        selected = select_primary_axes(figure)

        self.assertIs(selected, axis)
        plt.close(figure)

    def test_wrapped_open_files_handler_opens_export_folder_before_export(self):
        figure, axis = plt.subplots()
        axis.plot([0, 1, 2], [0, 1, 0], color="red")
        reset_axis = figure.add_axes([0.82, 0.08, 0.14, 0.04])
        reset_button = Button(reset_axis, "Reset")
        module = SimpleNamespace(
            figure=figure,
            animate=lambda frame: None,
            reset_button=reset_button,
        )
        entry = DemoEntry(
            identifier="demo_5",
            title="Minimal Two-Profile Study",
            description="Profile-focused view with a red/blue pair.",
            path=self.repo_dir / "demo_5.py",
        )

        decorate_demo_window(module, entry)
        with patch("demo_hub.subprocess.run") as run_mock:
            module._cycloidal_hub_controls["handle_open_file_location"](None)

        run_mock.assert_called_once()
        self.assertEqual(run_mock.call_args.args[0][0], "open")
        self.assertIn("Opened export folder", module._cycloidal_hub_controls["status_text"].get_text())

        plt.close(figure)


if __name__ == "__main__":
    unittest.main()

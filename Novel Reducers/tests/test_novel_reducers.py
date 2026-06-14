import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np  # noqa: E402

NOVEL_DIR = Path(__file__).resolve().parents[1]
if str(NOVEL_DIR) not in sys.path:
    sys.path.insert(0, str(NOVEL_DIR))

MECHANISMS = [
    "gerotor_pump",
    "capstan_drive",
    "non_circular_gears",
    "geneva_drive",
    "friction_disc_cvt",
    "antikythera_anomaly",
]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, NOVEL_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class NovelReducerTests(unittest.TestCase):
    def test_modules_build_animate_and_export(self):
        out_dir = Path(tempfile.mkdtemp())
        for name in MECHANISMS:
            with self.subTest(mechanism=name):
                module = _load(name)
                self.assertTrue(getattr(module, "_has_custom_layout", False))
                demo = module.demo
                self.assertIsNotNone(demo.fig)

                # Animate across a full cycle without raising.
                for phase in np.linspace(0.0, 2 * np.pi, 9):
                    demo._render(phase)

                # Auto-fit view limits stay finite for the default parameters.
                xlim = demo.ax.get_xlim()
                ylim = demo.ax.get_ylim()
                self.assertTrue(all(np.isfinite([*xlim, *ylim])))

                # Readout produces a string.
                self.assertIsInstance(module.readout(demo.values(), 0.0), str)

                # DXF export writes a non-empty drawing.
                path = out_dir / f"{name}.dxf"
                demo._write_dxf(path)
                self.assertTrue(path.exists() and path.stat().st_size > 0)

    def test_main_menu_lists_all_mechanisms(self):
        menu = _load("main_menu")
        filenames = {entry.filename for entry in menu.MECHANISMS}
        self.assertEqual(filenames, {f"{name}.py" for name in MECHANISMS})


if __name__ == "__main__":
    unittest.main()

import importlib.util
import sys
import unittest
from pathlib import Path


class ReducersHubTests(unittest.TestCase):
    def test_parent_hub_lists_all_reducer_families(self):
        reducers_root = Path(__file__).resolve().parents[2]
        module_path = reducers_root / "reducers_hub.py"
        spec = importlib.util.spec_from_file_location("reducers_hub", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        entries = module.build_entries(reducers_root)
        titles = [entry.title for entry in entries]

        self.assertEqual(
            titles,
            [
                "Cycloidal Drive Demo Hub",
                "Planetary",
                "Harmonic",
                "Logarithmic Drive",
            ],
        )
        self.assertEqual(entries[0].status, "Ready")
        self.assertEqual(entries[1].status, "Ready")
        self.assertEqual(entries[2].status, "Ready")
        self.assertEqual(entries[3].status, "Ready")

    def test_parent_hub_can_load_embedded_family_pages(self):
        reducers_root = Path(__file__).resolve().parents[2]
        module_path = reducers_root / "reducers_hub.py"
        spec = importlib.util.spec_from_file_location("reducers_hub_embedded", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        entries = module.build_entries(reducers_root)
        cycloidal_builder = module.load_family_page_builder(entries[0])
        planetary_builder = module.load_family_page_builder(entries[1])
        harmonic_builder = module.load_family_page_builder(entries[2])
        logarithmic_builder = module.load_family_page_builder(entries[3])

        self.assertTrue(callable(cycloidal_builder))
        self.assertTrue(callable(planetary_builder))
        self.assertTrue(callable(harmonic_builder))
        self.assertTrue(callable(logarithmic_builder))


if __name__ == "__main__":
    unittest.main()

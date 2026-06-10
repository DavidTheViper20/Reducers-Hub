import unittest

from harmonic_demo_common import aligned_pose_angle_for_parameter_change, coupled_tooth_counts


class HarmonicDemoCommonTests(unittest.TestCase):
    def test_flex_change_keeps_circular_two_teeth_ahead(self):
        flex_teeth, circular_teeth = coupled_tooth_counts("flex_teeth", 44, 42)
        self.assertEqual(flex_teeth, 44)
        self.assertEqual(circular_teeth, 46)

    def test_circular_change_keeps_flex_two_teeth_behind(self):
        flex_teeth, circular_teeth = coupled_tooth_counts("circular_teeth", 40, 50)
        self.assertEqual(flex_teeth, 48)
        self.assertEqual(circular_teeth, 50)

    def test_parameter_changes_snap_back_to_aligned_pose(self):
        self.assertEqual(aligned_pose_angle_for_parameter_change(1.75), 0.0)


if __name__ == "__main__":
    unittest.main()

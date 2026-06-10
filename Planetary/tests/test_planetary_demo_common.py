import math
import unittest

from planetary_demo_common import (
    DEFAULT_ANIMATION_FRAMES,
    aligned_pose_angle_for_parameter_change,
    animation_step_radians,
)


class PlanetaryDemoCommonTests(unittest.TestCase):
    def test_animation_step_increases_with_slider_value(self):
        self.assertGreater(animation_step_radians(140), animation_step_radians(24))

    def test_default_animation_step_is_40_percent_slower_than_legacy_behavior(self):
        legacy_step = (2.0 * math.pi) / DEFAULT_ANIMATION_FRAMES
        self.assertAlmostEqual(animation_step_radians(DEFAULT_ANIMATION_FRAMES), legacy_step * 0.6)

    def test_parameter_changes_snap_back_to_aligned_pose(self):
        self.assertEqual(aligned_pose_angle_for_parameter_change(2.75), 0.0)


if __name__ == "__main__":
    unittest.main()

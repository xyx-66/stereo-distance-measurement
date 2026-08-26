"""深度计算核心单元测试。"""

import unittest

import numpy as np

from stereo.distance import disparity_to_depth, distance_at


class TestDisparityToDepth(unittest.TestCase):
    def test_basic(self):
        disparity = np.array([[10.0], [0.0], [-2.0]], np.float32)
        depth, valid = disparity_to_depth(disparity, focal_px=700.0, baseline_mm=60.0)
        self.assertAlmostEqual(depth[0, 0], 700.0 * 60.0 / 10.0)
        self.assertTrue(valid[0, 0])
        self.assertFalse(valid[1, 0])
        self.assertFalse(valid[2, 0])

    def test_nan_invalid(self):
        disparity = np.array([[np.nan, 5.0]], np.float32)
        depth, valid = disparity_to_depth(disparity, 700.0, 60.0)
        self.assertFalse(valid[0, 0])
        self.assertTrue(valid[0, 1])


class TestDistanceAt(unittest.TestCase):
    def test_median_of_roi(self):
        depth = np.zeros((100, 100), np.float32)
        depth[40:60, 40:60] = 1234.0
        self.assertAlmostEqual(distance_at(depth, 50, 50, radius=15), 1234.0)

    def test_all_invalid_returns_none(self):
        depth = np.zeros((100, 100), np.float32)
        self.assertIsNone(distance_at(depth, 50, 50))


if __name__ == "__main__":
    unittest.main()
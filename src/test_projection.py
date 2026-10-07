"""Independent geometry checks: python -m unittest src.test_projection -v."""
import unittest

import numpy as np

from starter.kitti_io import KittiCalib, KittiObject, load_calib
from starter.projection import cam_to_image, velo_to_cam


class ProjectionTests(unittest.TestCase):
    def test_rigid_transform_and_rectification_order(self):
        rect = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1.]])
        extrinsic = np.column_stack([np.eye(3), [1, 2, 3]])
        calibration = KittiCalib(np.zeros((3, 4)), rect, extrinsic)
        np.testing.assert_allclose(velo_to_cam(np.array([[4, 5, 6.]]), calibration),
                                   [[-7, 5, 9]])

    def test_mask_depth_nonfinite_and_image_boundaries(self):
        projection = np.column_stack([np.eye(3), np.zeros(3)])
        points = np.array([[1, 2, 1], [0, 0, 1], [10, 2, 1], [2, 8, 1],
                           [-1, 2, 1], [1, 2, -1], [1, 2, 0],
                           [np.nan, 2, 1], [1, np.inf, 1], [1, 2, .1]])
        uv, depth, mask = cam_to_image(points, projection, (8, 10, 3))
        np.testing.assert_array_equal(mask, [True, True] + [False] * 8)
        np.testing.assert_allclose(uv, [[1, 2], [0, 0]])
        np.testing.assert_allclose(depth, [1, 1])

    def test_projection_uses_fourth_column(self):
        projection = np.column_stack([np.eye(3), [4, 6, 0]])
        uv, _, _ = cam_to_image(np.array([[2, 4, 2]]), projection, (20, 20))
        np.testing.assert_allclose(uv, [[3, 5]])

    def test_empty_cloud_and_invalid_lidar(self):
        calibration = KittiCalib(np.column_stack([np.eye(3), np.zeros(3)]),
                                np.eye(3), np.column_stack([np.eye(3), np.zeros(3)]))
        self.assertEqual(velo_to_cam(np.empty((0, 3)), calibration).shape, (0, 3))
        camera = velo_to_cam(np.array([[np.inf, 0, 1], [1, 2, 3]]), calibration)
        self.assertTrue(np.isnan(camera[0]).all())
        uv, depth, mask = cam_to_image(np.empty((0, 3)), calibration.P2, (10, 10))
        self.assertEqual((uv.shape, depth.shape, mask.shape), ((0, 2), (0,), (0,)))

    def test_synthetic_reference_point(self):
        calibration = load_calib('data/synthetic/training/calib/000000.txt')
        camera = velo_to_cam(np.array([[10, 0, 0]]), calibration)
        uv, _, mask = cam_to_image(camera, calibration.P2, (375, 1242, 3))
        self.assertTrue(mask[0])
        self.assertAlmostEqual(camera[0, 2], 9.73, delta=.03)
        np.testing.assert_allclose(uv, [[614, 175]], atol=3)

    def test_oriented_box_membership_and_bottom_center(self):
        from src.topic_a import points_in_box
        obj = KittiObject('Car', 0, 0, 0, np.zeros(4),
                          np.array([2., 2., 6.]), np.array([0., 1., 10.]), np.pi / 2)
        pts = np.array([[0, 0, 12.9], [1.1, 0, 10], [0, 1.1, 10], [0, -1.1, 10]])
        np.testing.assert_array_equal(points_in_box(pts, obj), [True, False, False, False])


if __name__ == '__main__':
    unittest.main()

"""立体校正：把左右图像校正为行对准，便于一维视差搜索。"""

from __future__ import annotations

import cv2
import numpy as np

from .config import CalibrationData


class StereoRectifier:
    """基于双目标定结果构建校正映射表。"""

    def __init__(self, calibration: CalibrationData | None, alpha: float = 0.0):
        self.calibration = calibration
        self.identity = calibration is None
        self.map_l: tuple[np.ndarray, np.ndarray] | None = None
        self.map_r: tuple[np.ndarray, np.ndarray] | None = None
        self.new_focal_px: float | None = None
        self.baseline_mm: float | None = None
        if calibration is not None:
            self._build_maps(alpha)

    def _build_maps(self, alpha: float) -> None:
        cal = self.calibration
        size = tuple(cal.image_size)
        mtx_l = np.array(cal.camera_matrix_l, np.float64)
        mtx_r = np.array(cal.camera_matrix_r, np.float64)
        dist_l = np.array(cal.dist_coeffs_l, np.float64)
        dist_r = np.array(cal.dist_coeffs_r, np.float64)
        rotation = np.array(cal.rotation, np.float64)
        translation = np.array(cal.translation, np.float64)

        r1, r2, p1, p2, q, _, _ = cv2.stereoRectify(
            mtx_l,
            dist_l,
            mtx_r,
            dist_r,
            size,
            rotation,
            translation,
            alpha=alpha,
            flags=cv2.CALIB_ZERO_DISPARITY,
        )
        self.map_l = cv2.initUndistortRectifyMap(
            mtx_l, dist_l, r1, p1, size, cv2.CV_16SC2
        )
        self.map_r = cv2.initUndistortRectifyMap(
            mtx_r, dist_r, r2, p2, size, cv2.CV_16SC2
        )
        self.new_focal_px = float(p1[0, 0])
        self.baseline_mm = float(np.linalg.norm(translation))

    def rectify(self, left: np.ndarray, right: np.ndarray):
        """输入左右 BGR 图，返回校正后的左右图。"""
        if self.identity:
            return left, right
        return (
            cv2.remap(left, self.map_l[0], self.map_l[1], cv2.INTER_LINEAR),
            cv2.remap(right, self.map_r[0], self.map_r[1], cv2.INTER_LINEAR),
        )
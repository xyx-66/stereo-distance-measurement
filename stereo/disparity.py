"""视差计算：SGBM 立体匹配，可选 WLS 滤波。"""

from __future__ import annotations

import cv2
import numpy as np

try:  # WLS 滤波需要 opencv-contrib-python
    import cv2.ximgproc as _ximgproc

    HAS_XIMGPROC = True
except ImportError:  # pragma: no cover
    _ximgproc = None
    HAS_XIMGPROC = False


class StereoMatcher:
    """封装 StereoSGBM（以及可选的 WLS 后处理）。"""

    def __init__(
        self,
        num_disparities: int = 64,
        block_size: int = 11,
        uniqueness_ratio: int = 10,
        speckle_window: int = 100,
        speckle_range: int = 32,
        p1_scale: int = 8,
        p2_scale: int = 32,
        use_wls: bool = False,
        wls_lambda: float = 8000.0,
        wls_sigma: float = 1.5,
    ):
        num_disparities = max(16, (int(num_disparities) // 16) * 16)
        block_size = max(3, int(block_size) | 1)  # 保证为奇数

        self.sgbm = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=num_disparities,
            blockSize=block_size,
            P1=p1_scale * block_size * block_size,
            P2=p2_scale * block_size * block_size,
            disp12MaxDiff=1,
            uniquenessRatio=uniqueness_ratio,
            speckleWindowSize=speckle_window,
            speckleRange=speckle_range,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
        )
        self.wls = None
        if use_wls and HAS_XIMGPROC:
            self.wls = _ximgproc.createDisparityWLSFilter(self.sgbm)
            self.wls.setLambda(wls_lambda)
            self.wls.setSigmaColor(wls_sigma)
        elif use_wls:
            print("[警告] 未安装 opencv-contrib-python，WLS 滤波已禁用")

    def compute(self, left: np.ndarray, right: np.ndarray) -> np.ndarray:
        """返回 float32 视差图，单位：像素。"""
        gray_l = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY) if left.ndim == 3 else left
        gray_r = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY) if right.ndim == 3 else right

        disp16 = self.sgbm.compute(gray_l, gray_r)
        if self.wls is not None:
            disp16_right = self.sgbm.compute(gray_r, gray_l)
            disp16 = self.wls.filter(disp16, gray_l, None, disp16_right)
        return disp16.astype(np.float32) / 16.0
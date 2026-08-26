"""深度与距离计算：Z = f * B / d。"""

from __future__ import annotations

import numpy as np

from .disparity import StereoMatcher
from .rectify import StereoRectifier


def disparity_to_depth(
    disparity: np.ndarray, focal_px: float, baseline_mm: float
) -> tuple[np.ndarray, np.ndarray]:
    """视差图 -> 深度图（毫米）。无效点（d <= 0 或非有限值）置 0。"""
    valid = (disparity > 0.0) & np.isfinite(disparity)
    depth = np.zeros_like(disparity, dtype=np.float32)
    depth[valid] = focal_px * baseline_mm / disparity[valid]
    return depth, valid


def distance_at(
    depth: np.ndarray,
    x: int,
    y: int,
    radius: int = 8,
    min_valid_ratio: float = 0.3,
) -> float | None:
    """取 (x, y) 邻域内有效深度的中位数作为该点距离（毫米）。

    有效深度占比过低时返回 None。
    """
    h, w = depth.shape
    x0, x1 = max(0, x - radius), min(w, x + radius + 1)
    y0, y1 = max(0, y - radius), min(h, y + radius + 1)
    patch = depth[y0:y1, x0:x1]
    values = patch[patch > 0]
    if values.size < min_valid_ratio * patch.size:
        return None
    return float(np.median(values))


class StereoDistanceMeter:
    """双目测距核心：立体校正 -> SGBM 匹配 -> 深度图。"""

    def __init__(
        self,
        rectifier: StereoRectifier,
        matcher: StereoMatcher,
        focal_px: float | None = None,
        baseline_mm: float | None = None,
    ):
        self.rectifier = rectifier
        self.matcher = matcher

        # 标定结果优先，否则使用命令行传入的近似值
        if rectifier is not None and rectifier.new_focal_px:
            self.focal_px = rectifier.new_focal_px
        else:
            self.focal_px = focal_px

        if rectifier is not None and rectifier.baseline_mm:
            self.baseline_mm = rectifier.baseline_mm
        else:
            self.baseline_mm = baseline_mm

        if not self.focal_px:
            raise ValueError("缺少焦距 focal_px（可用 --focal 指定或提供标定文件）")
        if not self.baseline_mm:
            raise ValueError("缺少基线 baseline_mm（可用 --baseline 指定或提供标定文件）")

    def process(self, left: np.ndarray, right: np.ndarray):
        """处理一帧：返回 (校正左图, 校正右图, 视差图, 深度图, 有效掩码)。"""
        left_r, right_r = self.rectifier.rectify(left, right)
        disparity = self.matcher.compute(left_r, right_r)
        depth, valid = disparity_to_depth(disparity, self.focal_px, self.baseline_mm)
        return left_r, right_r, disparity, depth, valid
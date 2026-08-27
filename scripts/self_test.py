from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stereo.disparity import StereoMatcher
from stereo.distance import disparity_to_depth, distance_at
from stereo.rectify import StereoRectifier


def make_synthetic_pair(
    width: int = 640, height: int = 480, disparity: int = 48, seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    """构造一张已知视差的纹理平面左右图。"""
    rng = np.random.default_rng(seed)
    plane = rng.integers(0, 256, (height, width + disparity), dtype=np.uint8)
    plane = cv2.GaussianBlur(plane, (0, 0), 1.2)
    # 添加多尺度结构，给 SGBM 提供稳定匹配特征
    for _ in range(80):
        x = int(rng.integers(0, width + disparity - 40))
        y = int(rng.integers(0, height - 40))
        r = int(rng.integers(5, 28))
        color = int(rng.integers(0, 256))
        cv2.circle(plane, (x, y), r, color, -1)
        cv2.rectangle(plane, (x, y), (x + r, y + r), 255 - color, 2)
    left = plane[:, :width]
    right = plane[:, disparity : disparity + width]
    return left, right


def main() -> int:
    focal_px, baseline_mm = 700.0, 60.0
    disparity_px = 48
    expected_mm = focal_px * baseline_mm / disparity_px

    print("生成合成双目图像对（视差 = 48 px）…")
    left, right = make_synthetic_pair(disparity=disparity_px)

    matcher = StereoMatcher(num_disparities=64, block_size=9, uniqueness_ratio=5)
    rectifier = StereoRectifier(None)  # 无标定 -> 恒等校正
    disp = matcher.compute(left, right)
    depth, valid = disparity_to_depth(disp, focal_px, baseline_mm)

    h, w = depth.shape
    radius = min(w, h) // 6
    measured = distance_at(depth, w // 2, h // 2, radius=radius)
    region = valid[h // 2 - radius : h // 2 + radius + 1, w // 2 - radius : w // 2 + radius + 1]
    valid_ratio = float(region.mean())

    print(f"理论距离: {expected_mm:.1f} mm")
    print(f"实测距离: {measured:.1f} mm")
    print(f"中心区域有效视差占比: {valid_ratio:.2%}")

    if measured is None:
        print("[FAIL] 中心区域无有效深度")
        return 1
    if valid_ratio < 0.5:
        print("[FAIL] 立体匹配质量不足")
        return 1
    error = abs(measured - expected_mm) / expected_mm
    print(f"相对误差: {error:.2%}")
    if error > 0.2:
        print("[FAIL] 误差超过 20%")
        return 1
    print("[PASS] 双目测距全链路自检通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

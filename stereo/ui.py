"""可视化辅助：FPS 统计、文字叠加、视差伪彩。"""

from __future__ import annotations

import time

import cv2
import numpy as np


class FpsCounter:
    """指数滑动平均的 FPS 统计。"""

    def __init__(self, alpha: float = 0.1):
        self.alpha = alpha
        self.fps = 0.0
        self._last = None

    def update(self) -> float:
        now = time.perf_counter()
        if self._last is not None:
            dt = now - self._last
            if dt > 0:
                instant = 1.0 / dt
                self.fps = (
                    instant
                    if self.fps == 0
                    else self.alpha * instant + (1 - self.alpha) * self.fps
                )
        self._last = now
        return self.fps


def put_text(
    frame: np.ndarray,
    text: str,
    org: tuple[int, int],
    color: tuple[int, int, int] = (0, 255, 0),
    scale: float = 0.7,
    thickness: int = 2,
) -> np.ndarray:
    """带黑色背景的文字叠加，保证可读性。"""
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    x, y = org
    cv2.rectangle(frame, (x - 4, y - h - 8), (x + w + 4, y + 6), (0, 0, 0), -1)
    cv2.putText(
        frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA
    )
    return frame


def colorize_disparity(
    disparity: np.ndarray, valid: np.ndarray | None = None
) -> np.ndarray:
    """把视差图转为伪彩图（近处偏红、远处偏蓝）。"""
    if valid is None:
        valid = disparity > 0
    disp = disparity.copy()
    values = disp[valid]
    colored = np.zeros((*disp.shape, 3), np.uint8)
    if values.size > 0 and values.max() > values.min():
        norm = np.zeros_like(disp)
        norm[valid] = (values - values.min()) / (values.max() - values.min()) * 255.0
        colored = cv2.applyColorMap(norm.astype(np.uint8), cv2.COLORMAP_TURBO)
    return colored
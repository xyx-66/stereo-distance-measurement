"""双目标定：棋盘格角点检测与相机内外参求解。"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from .config import CalibrationData

_CHESS_FLAGS = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE


def parse_pattern(text: str) -> tuple[int, int]:
    """把 '9x6' 解析为 (列数, 行数)，即棋盘内角点数。"""
    try:
        cols, rows = text.lower().split("x")
        return int(cols), int(rows)
    except ValueError as exc:
        raise ValueError("棋盘格尺寸格式应为 '列x行'，例如 --pattern 9x6") from exc


def find_chessboard(
    image: np.ndarray, pattern_size: tuple[int, int], refine: bool = True
) -> tuple[bool, np.ndarray | None]:
    """检测单张图像中的棋盘格角点。"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    found, corners = cv2.findChessboardCorners(gray, pattern_size, flags=_CHESS_FLAGS)
    if found and refine:
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
    return found, corners


def detect_pairs(
    left_images: Sequence[Path],
    right_images: Sequence[Path],
    pattern_size: tuple[int, int],
) -> tuple[list, list, list, int]:
    """批量检测左右图像对中的棋盘格角点。

    返回 (object_points, image_points_l, image_points_r, usable)。
    """
    object_points, image_points_l, image_points_r = [], [], []
    object_point = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    object_point[:, :2] = np.mgrid[
        0 : pattern_size[0], 0 : pattern_size[1]
    ].T.reshape(-1, 2)

    usable = 0
    for path_l, path_r in zip(left_images, right_images):
        img_l = cv2.imread(str(path_l))
        img_r = cv2.imread(str(path_r))
        if img_l is None or img_r is None:
            print(f"[跳过] 无法读取: {path_l} / {path_r}")
            continue
        ok_l, corners_l = find_chessboard(img_l, pattern_size)
        ok_r, corners_r = find_chessboard(img_r, pattern_size)
        if ok_l and ok_r:
            object_points.append(object_point)
            image_points_l.append(corners_l)
            image_points_r.append(corners_r)
            usable += 1
        else:
            print(f"[跳过] 角点不全: {Path(path_l).name}")
    return object_points, image_points_l, image_points_r, usable


def calibrate_stereo(
    object_points: list,
    image_points_l: list,
    image_points_r: list,
    image_size: tuple[int, int],
    square_size_mm: float,
) -> tuple[CalibrationData, float, tuple[float, float]]:
    """先分别单目标定获取内参初值，再双目标定求解外参。

    返回 (标定数据, 双目重投影误差, (左单目误差, 右单目误差))。
    """
    rms_l, mtx_l, dist_l, _, _ = cv2.calibrateCamera(
        object_points, image_points_l, image_size, None, None
    )
    rms_r, mtx_r, dist_r, _, _ = cv2.calibrateCamera(
        object_points, image_points_r, image_size, None, None
    )

    criteria = (cv2.TERM_CRITERIA_MAX_ITER + cv2.TERM_CRITERIA_EPS, 100, 1e-6)
    stereo_rms, mtx_l, dist_l, mtx_r, dist_r, R, T, E, F = cv2.stereoCalibrate(
        object_points,
        image_points_l,
        image_points_r,
        mtx_l,
        dist_l,
        mtx_r,
        dist_r,
        image_size,
        criteria=criteria,
        flags=cv2.CALIB_USE_INTRINSIC_GUESS,
    )

    # 物点以“1 格”为单位，乘以边长换算为毫米
    t_mm = (T * square_size_mm).tolist()

    calib = CalibrationData(
        image_size=[image_size[0], image_size[1]],
        camera_matrix_l=mtx_l.tolist(),
        camera_matrix_r=mtx_r.tolist(),
        dist_coeffs_l=dist_l.tolist(),
        dist_coeffs_r=dist_r.tolist(),
        rotation=R.tolist(),
        translation=t_mm,
        reprojection_error=float(stereo_rms),
    )
    return calib, float(stereo_rms), (float(rms_l), float(rms_r))
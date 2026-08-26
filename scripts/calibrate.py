#!/usr/bin/env python3
"""双目标定工具：实时采集棋盘格图像对并计算相机内外参。

用法示例：
  # 实时采集 + 标定（左摄像头 0，右摄像头 1，采集 15 对）
  python scripts/calibrate.py --capture --cam-l 0 --cam-r 1 --pairs 15 --square 24

  # 从已有图像对标定（图像对需同名，如 left_000.png / right_000.png）
  python scripts/calibrate.py --left-dir data/captures/left --right-dir data/captures/right --square 24

标定结果默认保存到 data/calibration.json。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stereo.calibration import calibrate_stereo, detect_pairs, find_chessboard, parse_pattern


def run_capture(
    cam_l: int, cam_r: int, pattern_size: tuple[int, int], target_pairs: int, out_dir: Path
) -> int:
    """从两个摄像头实时采集棋盘格图像对，保存到 out_dir/left 与 out_dir/right。"""
    out_dir = Path(out_dir)
    (out_dir / "left").mkdir(parents=True, exist_ok=True)
    (out_dir / "right").mkdir(parents=True, exist_ok=True)

    cap_l = cv2.VideoCapture(cam_l)
    cap_r = cv2.VideoCapture(cam_r)
    if not (cap_l.isOpened() and cap_r.isOpened()):
        raise RuntimeError("无法打开摄像头，请检查 --cam-l / --cam-r 编号")

    for cap in (cap_l, cap_r):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    saved = 0
    print("[采集] 空格=保存当前对，ESC=完成并开始标定")
    while saved < target_pairs:
        ok_l, left = cap_l.read()
        ok_r, right = cap_r.read()
        if not (ok_l and ok_r):
            continue

        found_l, corners_l = find_chessboard(left, pattern_size)
        found_r, corners_r = find_chessboard(right, pattern_size)
        found = found_l and found_r
        if found_l:
            cv2.drawChessboardCorners(left, pattern_size, corners_l, found_l)
        if found_r:
            cv2.drawChessboardCorners(right, pattern_size, corners_r, found_r)

        comb = np.hstack([left, right])
        status = f"[{'OK' if found else '未检测到'}] {saved}/{target_pairs}"
        cv2.putText(
            comb, status, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2, cv2.LINE_AA
        )
        h, w = comb.shape[:2]
        cv2.imshow("capture", cv2.resize(comb, (w // 2, h // 2)))

        key = cv2.waitKey(30) & 0xFF
        if key == 27:  # ESC
            break
        if key == 32 and found:  # 空格
            idx = f"{saved:03d}"
            cv2.imwrite(str(out_dir / "left" / f"left_{idx}.png"), left)
            cv2.imwrite(str(out_dir / "right" / f"right_{idx}.png"), right)
            saved += 1
            print(f"[保存] 第 {saved}/{target_pairs} 对")

    cap_l.release()
    cap_r.release()
    cv2.destroyAllWindows()
    return saved


def run_calibration(
    left_dir: Path, right_dir: Path, pattern_size: tuple[int, int], square_mm: float, out_path: Path
) -> None:
    """从图像目录执行双目标定并保存结果。"""
    left_dir, right_dir = Path(left_dir), Path(right_dir)
    left_images = sorted(list(left_dir.glob("*.png")) + list(left_dir.glob("*.jpg")))
    right_images = sorted(list(right_dir.glob("*.png")) + list(right_dir.glob("*.jpg")))
    common = sorted(set(p.name for p in left_images) & set(p.name for p in right_images))
    pairs = [(left_dir / n, right_dir / n) for n in common]
    if len(pairs) < 3:
        raise SystemExit(f"有效图像对不足（{len(pairs)} 对），至少需要 3 对，建议 10~20 对")

    object_points, image_points_l, image_points_r, usable = detect_pairs(
        [p[0] for p in pairs], [p[1] for p in pairs], pattern_size
    )
    if usable < 3:
        raise SystemExit(f"角点检测成功的图像对不足（{usable}/3），请调整光照或棋盘格角度")

    probe = cv2.imread(str(pairs[0][0]))
    h, w = probe.shape[:2]
    calib, stereo_rms, mono_rms = calibrate_stereo(
        object_points, image_points_l, image_points_r, (w, h), square_mm
    )
    calib.save(out_path)

    print(f"成功使用 {usable} 对图像")
    print(f"单目重投影误差 L={mono_rms[0]:.4f} px, R={mono_rms[1]:.4f} px")
    print(f"双目重投影误差 {stereo_rms:.4f} px")
    print(f"焦距 f = {calib.camera_matrix_l[0][0]:.2f} px")
    print(f"基线 B = {calib.baseline_mm:.2f} mm")
    print(f"标定结果已保存: {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="双目标定：实时采集棋盘格图像对并计算内外参",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--pattern", default="9x6", help="棋盘格内角点 列x行")
    parser.add_argument("--square", type=float, default=24.0, help="棋盘格边长（毫米）")
    parser.add_argument("--out", default="data/calibration.json", help="标定结果输出路径")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture", action="store_true", help="实时采集模式")
    mode.add_argument("--left-dir", type=str, help="左相机图像目录（离线模式）")
    mode.add_argument("--right-dir", type=str, help="右相机图像目录（离线模式）")

    parser.add_argument("--cam-l", type=int, default=0, help="左摄像头编号")
    parser.add_argument("--cam-r", type=int, default=1, help="右摄像头编号")
    parser.add_argument("--pairs", type=int, default=15, help="计划采集的图像对数量")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pattern_size = parse_pattern(args.pattern)

    if args.capture:
        capture_dir = Path("data/captures")
        saved = run_capture(args.cam_l, args.cam_r, pattern_size, args.pairs, capture_dir)
        if saved == 0:
            raise SystemExit("未采集到任何图像对，请让棋盘格同时出现在两个画面中")
        run_calibration(
            capture_dir / "left", capture_dir / "right", pattern_size, args.square, Path(args.out)
        )
    else:
        if not args.left_dir or not args.right_dir:
            raise SystemExit("离线模式需要同时指定 --left-dir 与 --right-dir")
        run_calibration(
            Path(args.left_dir), Path(args.right_dir), pattern_size, args.square, Path(args.out)
        )


if __name__ == "__main__":
    main()
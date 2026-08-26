#!/usr/bin/env python3
"""双目实时测距主程序：Z = f * B / d。

用法示例：
  # 无标定近似模式（f 与 B 需要根据实际相机估计）
  python scripts/distance.py --cam-l 0 --cam-r 1 --focal 700 --baseline 60

  # 标定后模式（推荐）
  python scripts/distance.py --cam-l 0 --cam-r 1 --calib data/calibration.json

  # 用视频文件代替摄像头
  python scripts/distance.py --left-file data/left.mp4 --right-file data/right.mp4 --calib data/calibration.json

操作：左键点击测距 | F 切换人脸测距 | D 显示/隐藏视差窗口 | Q/ESC 退出
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stereo.capture import StereoCapture
from stereo.config import CalibrationData
from stereo.disparity import StereoMatcher
from stereo.distance import StereoDistanceMeter, distance_at
from stereo.rectify import StereoRectifier
from stereo.ui import FpsCounter, colorize_disparity, put_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="双目实时测距：立体校正 + SGBM 视差 + Z = f·B/d",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    src = parser.add_argument_group("视频源")
    src.add_argument("--cam-l", type=int, default=0, help="左摄像头编号")
    src.add_argument("--cam-r", type=int, default=1, help="右摄像头编号")
    src.add_argument("--left-file", type=str, default=None, help="左视频文件（与摄像头二选一）")
    src.add_argument("--right-file", type=str, default=None, help="右视频文件")

    cal = parser.add_argument_group("相机参数")
    cal.add_argument("--calib", type=str, default=None, help="双目标定结果 JSON（data/calibration.json）")
    cal.add_argument("--focal", type=float, default=700.0, help="近似焦距（像素），未标定时使用")
    cal.add_argument("--baseline", type=float, default=60.0, help="近似基线（毫米），未标定时使用")
    cal.add_argument("--max-distance", type=float, default=3000.0, help="视差图显示的距离上限（毫米）")

    match = parser.add_argument_group("立体匹配")
    match.add_argument("--num-disparities", type=int, default=64, help="视差搜索范围（16 的倍数）")
    match.add_argument("--block-size", type=int, default=11, help="匹配块大小（奇数）")
    match.add_argument("--wls", action="store_true", help="启用 WLS 滤波（需 opencv-contrib-python）")

    view = parser.add_argument_group("显示")
    view.add_argument("--scale", type=float, default=0.6, help="显示缩放比例")
    view.add_argument("--face", action="store_true", help="启用人脸测距演示")
    return parser.parse_args()


def build_meter(args: argparse.Namespace) -> StereoDistanceMeter:
    calib = None
    if args.calib:
        calib = CalibrationData.load(args.calib)
        print(f"[标定] 已加载 {args.calib}，基线 {calib.baseline_mm:.1f} mm")
    rectifier = StereoRectifier(calib)
    matcher = StereoMatcher(
        num_disparities=args.num_disparities, block_size=args.block_size, use_wls=args.wls
    )
    meter = StereoDistanceMeter(
        rectifier, matcher, focal_px=args.focal, baseline_mm=args.baseline
    )
    print(f"[测距] 焦距 {meter.focal_px:.1f} px，基线 {meter.baseline_mm:.1f} mm")
    return meter


def main() -> None:
    args = parse_args()
    meter = build_meter(args)

    if args.left_file and args.right_file:
        capture = StereoCapture(args.left_file, args.right_file, size=None)
    else:
        capture = StereoCapture(args.cam_l, args.cam_r)

    face_cascade = None
    if args.face:
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    fps = FpsCounter()
    click_pt: tuple[int, int] | None = None

    def on_mouse(event, x, y, flags, param) -> None:
        nonlocal click_pt
        if event == cv2.EVENT_LBUTTONDOWN:
            click_pt = (x, y)

    win_left = "left (click to measure)"
    win_depth = "disparity"
    cv2.namedWindow(win_left)
    cv2.setMouseCallback(win_left, on_mouse)
    show_disparity = True

    print("操作提示：左键点击测距 | F 人脸测距 | D 视差窗口 | Q/ESC 退出")

    while True:
        ok, left, right = capture.read()
        if not ok:
            print("[警告] 读取帧失败，等待重试…")
            if cv2.waitKey(30) & 0xFF in (27, ord("q")):
                break
            continue

        left_r, right_r, disparity, depth, valid = meter.process(left, right)
        fps.update()
        h, w = left_r.shape[:2]

        # ---- 左视图叠加 ----
        view = left_r.copy()
        put_text(view, f"FPS: {fps.fps:.1f}", (10, 30))

        cx, cy = w // 2, h // 2
        dist_center = distance_at(depth, cx, cy)
        put_text(
            view,
            f"center: {dist_center / 1000:.2f} m" if dist_center else "center: --",
            (10, 60),
        )
        cv2.line(view, (cx - 20, cy), (cx + 20, cy), (0, 255, 0), 1)
        cv2.line(view, (cx, cy - 20), (cx, cy + 20), (0, 255, 0), 1)

        if click_pt is not None:
            ix, iy = int(click_pt[0] / args.scale), int(click_pt[1] / args.scale)
            dist_click = distance_at(depth, ix, iy)
            cv2.drawMarker(view, (ix, iy), (0, 0, 255), cv2.MARKER_CROSS, 24, 2)
            put_text(
                view,
                f"{dist_click / 1000:.2f} m" if dist_click else "-- m",
                (ix + 14, iy - 12),
                (0, 0, 255),
            )

        if face_cascade is not None:
            gray = cv2.cvtColor(left_r, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(60, 60))
            for fx, fy, fw, fh in faces:
                d = distance_at(depth, fx + fw // 2, fy + fh // 2, radius=max(8, fw // 6))
                label = f"{d / 1000:.2f} m" if d else "-- m"
                cv2.rectangle(view, (fx, fy), (fx + fw, fy + fh), (0, 255, 255), 2)
                put_text(view, label, (fx, fy - 8), (0, 255, 255))

        # ---- 视差/深度伪彩图 ----
        mask = valid & (depth <= args.max_distance)
        disp_display = np.where(mask, disparity, 0.0)
        colored = colorize_disparity(disp_display, mask)
        put_text(colored, f"disparity (max {args.max_distance / 1000:.1f} m)", (10, 30),
                 (255, 255, 255))

        # ---- 缩放显示 ----
        new_w, new_h = int(w * args.scale), int(h * args.scale)
        if args.scale != 1.0:
            view = cv2.resize(view, (new_w, new_h), interpolation=cv2.INTER_AREA)
            colored = cv2.resize(colored, (new_w, new_h), interpolation=cv2.INTER_AREA)

        cv2.imshow(win_left, view)
        if show_disparity:
            cv2.imshow(win_depth, colored)

        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q")):
            break
        elif key in (ord("f"), ord("F")):
            face_cascade = (
                None
                if face_cascade is not None
                else cv2.CascadeClassifier(
                    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                )
            )
            print("[人脸] " + ("开" if face_cascade is not None else "关"))
        elif key in (ord("d"), ord("D")):
            show_disparity = not show_disparity
            if not show_disparity:
                cv2.destroyWindow(win_depth)

    capture.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
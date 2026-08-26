"""双摄像头 / 双视频流读取。"""

from __future__ import annotations

import cv2


class StereoCapture:
    """封装左右两个 VideoCapture（摄像头或视频文件）。"""

    def __init__(self, source_l, source_r, size: tuple[int, int] | None = (1280, 720)):
        self.cap_l = cv2.VideoCapture(source_l)
        self.cap_r = cv2.VideoCapture(source_r)
        if size:
            for cap in (self.cap_l, self.cap_r):
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        if not (self.cap_l.isOpened() and self.cap_r.isOpened()):
            self.release()
            raise RuntimeError("无法打开双目视频源，请检查摄像头编号或文件路径")

    def read(self) -> tuple[bool, cv2.Mat, cv2.Mat]:
        ok_l, frame_l = self.cap_l.read()
        ok_r, frame_r = self.cap_r.read()
        return (ok_l and ok_r), frame_l, frame_r

    def release(self) -> None:
        self.cap_l.release()
        self.cap_r.release()
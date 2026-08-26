"""配置数据类：双目标定结果的读写。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class CalibrationData:
    """双目标定结果。长度单位为毫米（平移向量已按棋盘格边长换算）。"""

    image_size: list[int]  # [width, height]
    camera_matrix_l: list[list[float]]
    camera_matrix_r: list[list[float]]
    dist_coeffs_l: list[float]
    dist_coeffs_r: list[float]
    rotation: list[list[float]]  # R: 右相机相对左相机的旋转
    translation: list[list[float]]  # T: 右相机相对左相机的平移（毫米）
    reprojection_error: float = 0.0  # 双目重投影误差（像素）

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationData":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @property
    def baseline_mm(self) -> float:
        """基线长度 = 平移向量模长（毫米）。"""
        t = self.translation
        return float((t[0][0] ** 2 + t[1][0] ** 2 + t[2][0] ** 2) ** 0.5)
from typing import Tuple

import numpy as np

from src.applications.contour_matching_tester.service.i_contour_matching_tester_service import IContourMatchingTesterService


class _StubWorkpiece:
    def __init__(self, wp_id: int, name: str, contour: np.ndarray):
        self.workpieceId = wp_id
        self.name = name
        self._contour = contour

    def get_main_contour(self) -> np.ndarray:
        return self._contour

    def get_spray_pattern_contours(self) -> list:
        return []

    def get_spray_pattern_fills(self) -> list:
        return []

    def __str__(self) -> str:
        return f"[{self.workpieceId}] {self.name}"


_STUB_WORKPIECES = [
    _StubWorkpiece(1, "Square",   np.array([[50, 50], [200, 50], [200, 200], [50, 200]], dtype=np.float32)),
    _StubWorkpiece(2, "Triangle", np.array([[125, 30], [30, 220], [220, 220]], dtype=np.float32)),
    _StubWorkpiece(3, "Rectangle", np.array([[30, 80], [290, 80], [290, 170], [30, 170]], dtype=np.float32)),
]


class StubContourMatchingTesterService(IContourMatchingTesterService):

    def get_workpieces(self) -> list:
        print("[ContourMatchingTester] get_workpieces → 3 stub workpieces")
        return list(_STUB_WORKPIECES)


    def get_latest_contours(self) -> list:
        print("[ContourMatchingTester] get_latest_contours → []")
        return []

    def run_matching(self, workpieces: list, contours: list) -> Tuple[dict, int]:
        print(f"[ContourMatchingTester] run_matching → {len(workpieces)} WPs, {len(contours)} contours")
        return {"workpieces": [], "orientations": [], "mlConfidences": [], "mlResults": []}, 0


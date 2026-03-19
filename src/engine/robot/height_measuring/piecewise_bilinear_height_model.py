from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
from matplotlib.tri import Triangulation

from src.engine.robot.height_measuring.depth_map_data import DepthMapData

MARKER_LABELS = {
    0: "top left",
    1: "top mid",
    2: "top right",
    3: "mid left",
    4: "mid mid",
    5: "mid right",
    6: "bottom left",
    8: "bottom right",
    100: "center 0/1/3/4",
    101: "center 1/2/4/5",
    102: "center 3/4/6",
    103: "center 4/5/8",
}

TOP_LEFT_CENTER = 100
TOP_RIGHT_CENTER = 101
BOTTOM_LEFT_CENTER = 102
BOTTOM_RIGHT_CENTER = 103

_VERIFICATION_TRIANGLES = [
    ("top left verify", (0, 4, 3)),
    ("top right verify", (1, 5, 4)),
    ("bottom left verify", (3, 4, 6)),
    ("bottom right verify", (4, 5, 8)),
]


@dataclass(frozen=True)
class TrianglePatch:
    name: str
    marker_ids: tuple[int, int, int]
    points: np.ndarray  # shape (3, 3): [x, y, z]

    def centroid(self) -> tuple[float, float, float]:
        centroid = self.points.mean(axis=0)
        return float(centroid[0]), float(centroid[1]), float(centroid[2])


@dataclass(frozen=True)
class VerificationPoint:
    name: str
    patch_name: str
    x: float
    y: float
    predicted_height: float


class PiecewiseBilinearHeightModel:
    """Triangle-based height model over the calibrated marker layout.

    The class name is kept for compatibility with existing call sites, but the
    interpolation surface now uses piecewise planar triangles instead of quad
    bilinear patches.
    """

    def __init__(self, points_by_id: dict[int, tuple[float, float, float]]):
        self._points_by_id = points_by_id
        self._triangles = self._build_triangles(points_by_id)

    @classmethod
    def from_depth_map(cls, data: DepthMapData) -> "PiecewiseBilinearHeightModel":
        marker_ids = [int(v) for v in data.marker_ids]
        if not marker_ids and len(data.points) == 8:
            marker_ids = [0, 1, 2, 3, 4, 5, 6, 8]

        points_by_id: dict[int, tuple[float, float, float]] = {}
        for marker_id, point in zip(marker_ids, data.points):
            if len(point) < 3:
                continue
            points_by_id[int(marker_id)] = (float(point[0]), float(point[1]), float(point[2]))
        return cls(points_by_id)

    def is_supported(self) -> bool:
        return len(self.verification_points()) == 4

    def patches(self) -> List[TrianglePatch]:
        return list(self._triangles)

    def points_by_id(self) -> dict[int, tuple[float, float, float]]:
        return dict(self._points_by_id)

    def triangulation_data(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        point_items = sorted(self._points_by_id.items())
        index_by_id = {marker_id: idx for idx, (marker_id, _) in enumerate(point_items)}
        x = np.array([point[0] for _, point in point_items], dtype=float)
        y = np.array([point[1] for _, point in point_items], dtype=float)
        z = np.array([point[2] for _, point in point_items], dtype=float)
        triangles = np.array(
            [
                [index_by_id[a], index_by_id[b], index_by_id[c]]
                for _, (a, b, c) in self._triangle_layout(self._points_by_id)
                if all(marker_id in index_by_id for marker_id in (a, b, c))
            ],
            dtype=int,
        )
        return x, y, z, triangles

    def triangulation(self) -> Triangulation | None:
        x, y, _, triangles = self.triangulation_data()
        if len(triangles) == 0:
            return None
        return Triangulation(x, y, triangles)

    def verification_points(self) -> list[VerificationPoint]:
        points: list[VerificationPoint] = []
        for name, marker_ids in _VERIFICATION_TRIANGLES:
            if not all(marker_id in self._points_by_id for marker_id in marker_ids):
                continue
            base_triangle = np.array(
                [self._points_by_id[marker_id] for marker_id in marker_ids],
                dtype=float,
            )
            centroid = base_triangle.mean(axis=0)
            predicted = self.interpolate_height(float(centroid[0]), float(centroid[1]))
            if predicted is None:
                predicted = float(centroid[2])
            points.append(
                VerificationPoint(
                    name=name,
                    patch_name="/".join(str(marker_id) for marker_id in marker_ids),
                    x=float(centroid[0]),
                    y=float(centroid[1]),
                    predicted_height=float(predicted),
                )
            )
        return points

    def interpolate_height(self, x: float, y: float) -> float | None:
        point = np.array([float(x), float(y)], dtype=float)
        for triangle in self._triangles:
            bary = self._barycentric_weights(point, triangle.points[:, :2])
            if bary is None:
                continue
            if min(bary) >= -1e-9:
                z = float(np.dot(bary, triangle.points[:, 2]))
                return z
        return None

    @staticmethod
    def _build_triangles(points_by_id: dict[int, tuple[float, float, float]]) -> list[TrianglePatch]:
        triangles: list[TrianglePatch] = []
        for name, marker_ids in PiecewiseBilinearHeightModel._triangle_layout(points_by_id):
            if not all(marker_id in points_by_id for marker_id in marker_ids):
                continue
            triangles.append(
                TrianglePatch(
                    name=name,
                    marker_ids=marker_ids,
                    points=np.array([points_by_id[marker_id] for marker_id in marker_ids], dtype=float),
                )
            )

        return triangles

    @staticmethod
    def _triangle_layout(points_by_id: dict[int, tuple[float, float, float]]) -> list[tuple[str, tuple[int, int, int]]]:
        layout: list[tuple[str, tuple[int, int, int]]] = []

        if all(marker_id in points_by_id for marker_id in (0, 1, 3, 4, TOP_LEFT_CENTER)):
            layout.extend(
                [
                    ("top_left_north", (0, 1, TOP_LEFT_CENTER)),
                    ("top_left_east", (1, 4, TOP_LEFT_CENTER)),
                    ("top_left_south", (4, 3, TOP_LEFT_CENTER)),
                    ("top_left_west", (3, 0, TOP_LEFT_CENTER)),
                ]
            )
        else:
            layout.extend(
                [
                    ("top_left_outer", (0, 1, 4)),
                    ("top_left_inner", (0, 4, 3)),
                ]
            )

        if all(marker_id in points_by_id for marker_id in (1, 2, 4, 5, TOP_RIGHT_CENTER)):
            layout.extend(
                [
                    ("top_right_north", (1, 2, TOP_RIGHT_CENTER)),
                    ("top_right_east", (2, 5, TOP_RIGHT_CENTER)),
                    ("top_right_south", (5, 4, TOP_RIGHT_CENTER)),
                    ("top_right_west", (4, 1, TOP_RIGHT_CENTER)),
                ]
            )
        else:
            layout.extend(
                [
                    ("top_right_outer", (1, 2, 5)),
                    ("top_right_inner", (1, 5, 4)),
                ]
            )

        if all(marker_id in points_by_id for marker_id in (3, 4, 6, BOTTOM_LEFT_CENTER)):
            layout.extend(
                [
                    ("bottom_left_a", (3, 4, BOTTOM_LEFT_CENTER)),
                    ("bottom_left_b", (4, 6, BOTTOM_LEFT_CENTER)),
                    ("bottom_left_c", (6, 3, BOTTOM_LEFT_CENTER)),
                ]
            )
        else:
            layout.append(("bottom_left", (3, 4, 6)))

        layout.append(("bottom_center", (4, 6, 8)))

        if all(marker_id in points_by_id for marker_id in (4, 5, 8, BOTTOM_RIGHT_CENTER)):
            layout.extend(
                [
                    ("bottom_right_a", (4, 5, BOTTOM_RIGHT_CENTER)),
                    ("bottom_right_b", (5, 8, BOTTOM_RIGHT_CENTER)),
                    ("bottom_right_c", (8, 4, BOTTOM_RIGHT_CENTER)),
                ]
            )
        else:
            layout.append(("bottom_right", (4, 5, 8)))

        return layout

    @staticmethod
    def _barycentric_weights(point: np.ndarray, triangle_xy: np.ndarray) -> np.ndarray | None:
        a = triangle_xy[0]
        b = triangle_xy[1]
        c = triangle_xy[2]
        v0 = b - a
        v1 = c - a
        v2 = point - a
        denom = v0[0] * v1[1] - v1[0] * v0[1]
        if abs(float(denom)) < 1e-9:
            return None
        inv = 1.0 / float(denom)
        w1 = (v2[0] * v1[1] - v1[0] * v2[1]) * inv
        w2 = (v0[0] * v2[1] - v2[0] * v0[1]) * inv
        w0 = 1.0 - w1 - w2
        return np.array([w0, w1, w2], dtype=float)

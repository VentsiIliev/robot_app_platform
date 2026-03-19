from __future__ import annotations

from dataclasses import dataclass
import math
import re

import numpy as np
from matplotlib.tri import Triangulation

from src.engine.robot.height_measuring.depth_map_data import DepthMapData


@dataclass(frozen=True)
class AreaGridVerificationPoint:
    name: str
    source: str
    interpolation_mode: str
    x: float
    y: float
    predicted_height: float


@dataclass(frozen=True)
class AreaGridCellPrediction:
    row: int
    col: int
    source: str
    interpolation_mode: str
    x: float
    y: float
    z: float


class AreaGridHeightModel:
    """Grid-aware height model that reconstructs missing planned nodes for rendering and inference."""

    _LABEL_RE = re.compile(r"^r(\d+)c(\d+)$")

    def __init__(
        self,
        rows: int,
        cols: int,
        planned_xy_by_rc: dict[tuple[int, int], tuple[float, float]],
        measured_xyz_by_rc: dict[tuple[int, int], tuple[float, float, float]],
        unavailable_rc: set[tuple[int, int]] | None = None,
    ):
        self._rows = int(rows)
        self._cols = int(cols)
        self._planned_xy_by_rc = dict(planned_xy_by_rc)
        self._measured_xyz_by_rc = dict(measured_xyz_by_rc)
        self._unavailable_rc = set(unavailable_rc or set())
        self._completed_xyz_by_rc: dict[tuple[int, int], tuple[float, float, float]] = {}
        self._status_by_rc: dict[tuple[int, int], str] = {}
        self._triangulation_cache = None
        self._triangles_cache = None
        self._complete_grid()

    @classmethod
    def from_depth_map(cls, data: DepthMapData) -> "AreaGridHeightModel":
        rows = int(getattr(data, "grid_rows", 0) or 0)
        cols = int(getattr(data, "grid_cols", 0) or 0)

        planned_xy_by_rc: dict[tuple[int, int], tuple[float, float]] = {}
        planned_points = [list(point) for point in getattr(data, "planned_points", [])]
        planned_labels = [str(label) for label in getattr(data, "planned_point_labels", [])]
        for label, point in zip(planned_labels, planned_points):
            parsed = cls._parse_label(label, rows, cols)
            if parsed is None or len(point) < 2:
                continue
            planned_xy_by_rc[parsed] = (float(point[0]), float(point[1]))

        measured_xyz_by_rc: dict[tuple[int, int], tuple[float, float, float]] = {}
        measured_points = [list(point) for point in getattr(data, "points", [])]
        measured_labels = [str(label) for label in getattr(data, "point_labels", [])]
        for label, point in zip(measured_labels, measured_points):
            parsed = cls._parse_label(label, rows, cols)
            if parsed is None or len(point) < 3:
                continue
            measured_xyz_by_rc[parsed] = (float(point[0]), float(point[1]), float(point[2]))

        if not planned_xy_by_rc and rows >= 2 and cols >= 2:
            for label, point in zip(measured_labels, measured_points):
                parsed = cls._parse_label(label, rows, cols)
                if parsed is None or len(point) < 2:
                    continue
                planned_xy_by_rc[parsed] = (float(point[0]), float(point[1]))

        unavailable_rc = {
            parsed
            for label in getattr(data, "unavailable_point_labels", [])
            if (parsed := cls._parse_label(str(label), rows, cols)) is not None
        }

        return cls(
            rows=rows,
            cols=cols,
            planned_xy_by_rc=planned_xy_by_rc,
            measured_xyz_by_rc=measured_xyz_by_rc,
            unavailable_rc=unavailable_rc,
        )

    @staticmethod
    def _parse_label(label: str, rows: int, cols: int) -> tuple[int, int] | None:
        match = AreaGridHeightModel._LABEL_RE.match(label)
        if match is None:
            return None
        row_idx = int(match.group(1)) - 1
        col_idx = int(match.group(2)) - 1
        if not (0 <= row_idx < rows and 0 <= col_idx < cols):
            return None
        return row_idx, col_idx

    def is_supported(self) -> bool:
        return self._rows >= 2 and self._cols >= 2 and len(self._completed_xyz_by_rc) >= 4

    def point_items(self) -> list[tuple[str, tuple[float, float, float]]]:
        items: list[tuple[str, tuple[float, float, float]]] = []
        for (row_idx, col_idx), point in sorted(self._completed_xyz_by_rc.items()):
            items.append((f"r{row_idx + 1}c{col_idx + 1}", point))
        return items

    def point_status_items(self) -> list[tuple[str, tuple[float, float, float], str]]:
        items: list[tuple[str, tuple[float, float, float], str]] = []
        for (row_idx, col_idx), point in sorted(self._completed_xyz_by_rc.items()):
            label = f"r{row_idx + 1}c{col_idx + 1}"
            items.append((label, point, self._status_by_rc.get((row_idx, col_idx), "measured")))
        return items

    def missing_labels(self) -> list[str]:
        labels: list[str] = []
        for row_idx in range(self._rows):
            for col_idx in range(self._cols):
                key = (row_idx, col_idx)
                if key in self._planned_xy_by_rc and key not in self._completed_xyz_by_rc:
                    labels.append(f"r{row_idx + 1}c{col_idx + 1}")
        return labels

    def triangulation(self) -> Triangulation | None:
        data = self.triangulation_data()
        if data is None:
            return None
        x, y, _z, triangles = data
        if len(triangles) == 0:
            return None
        return Triangulation(x, y, triangles)

    def triangulation_data(self):
        if len(self._completed_xyz_by_rc) < 3:
            return None
        if self._triangulation_cache is not None:
            return self._triangulation_cache

        point_items = sorted(self._completed_xyz_by_rc.items())
        x = np.array([point[0] for _, point in point_items], dtype=float)
        y = np.array([point[1] for _, point in point_items], dtype=float)
        z = np.array([point[2] for _, point in point_items], dtype=float)
        tri = Triangulation(x, y)
        triangles = np.array(tri.triangles, dtype=int)
        self._triangulation_cache = (x, y, z, triangles)
        self._triangles_cache = [
            np.array(
                [
                    [x[a], y[a], z[a]],
                    [x[b], y[b], z[b]],
                    [x[c], y[c], z[c]],
                ],
                dtype=float,
            )
            for a, b, c in triangles
        ]
        return self._triangulation_cache

    def interpolate_height(self, x: float, y: float) -> tuple[float | None, str]:
        z, mode = self._interpolate_from_completed(float(x), float(y))
        return z, mode

    def verification_points(self) -> list[AreaGridVerificationPoint]:
        if not self.is_supported():
            return []

        targets = [
            ("top left verify", 0, 0, 1, 1),
            ("top right verify", 0, self._cols - 2, 1, -1),
            ("bottom left verify", self._rows - 2, 0, -1, 1),
            ("bottom right verify", self._rows - 2, self._cols - 2, -1, -1),
        ]

        used_cells: set[tuple[int, int]] = set()
        points: list[AreaGridVerificationPoint] = []
        for name, start_row, start_col, row_step, col_step in targets:
            prediction = self._find_prediction(start_row, start_col, row_step, col_step, used_cells)
            if prediction is None:
                continue
            used_cells.add((prediction.row, prediction.col))
            points.append(
                AreaGridVerificationPoint(
                    name=name,
                    source=prediction.source,
                    interpolation_mode=prediction.interpolation_mode,
                    x=prediction.x,
                    y=prediction.y,
                    predicted_height=prediction.z,
                )
            )
        return points

    def _complete_grid(self) -> None:
        self._completed_xyz_by_rc = dict(self._measured_xyz_by_rc)
        self._status_by_rc = {key: "measured" for key in self._measured_xyz_by_rc}

        pending = sorted(
            key for key in self._planned_xy_by_rc
            if key not in self._completed_xyz_by_rc
        )
        for key in pending:
            x, y = self._planned_xy_by_rc[key]
            z, mode = self._estimate_missing_node(key)
            if z is None:
                continue
            self._completed_xyz_by_rc[key] = (float(x), float(y), float(z))
            self._status_by_rc[key] = mode

    def _estimate_missing_node(self, key: tuple[int, int]) -> tuple[float | None, str]:
        x, y = self._planned_xy_by_rc[key]
        local_estimates: list[float] = []
        row_idx, col_idx = key
        neighbor_cells = [
            (row_idx - 1, col_idx - 1),
            (row_idx - 1, col_idx),
            (row_idx, col_idx - 1),
            (row_idx, col_idx),
        ]
        for cell_row, cell_col in neighbor_cells:
            if not (0 <= cell_row < self._rows - 1 and 0 <= cell_col < self._cols - 1):
                continue
            estimate = self._interpolate_in_cell(
                cell_row,
                cell_col,
                float(x),
                float(y),
                points_by_rc=self._measured_xyz_by_rc,
                allow_extrapolation=True,
            )
            if estimate[0] is not None:
                local_estimates.append(float(estimate[0]))

        if local_estimates:
            return float(sum(local_estimates) / len(local_estimates)), "cell-estimated"

        return self._interpolate_from_known(float(x), float(y))

    def _interpolate_from_known(self, x: float, y: float) -> tuple[float | None, str]:
        cell_hit = self._interpolate_by_cell(float(x), float(y), self._measured_xyz_by_rc)
        if cell_hit[0] is not None:
            return cell_hit
        if len(self._measured_xyz_by_rc) >= 3:
            z, mode = self._interpolate_from_points(self._measured_xyz_by_rc, x, y)
            if z is not None:
                return z, mode
        return None, "none"

    def _interpolate_from_completed(self, x: float, y: float) -> tuple[float | None, str]:
        cell_hit = self._interpolate_by_cell(float(x), float(y), self._completed_xyz_by_rc)
        if cell_hit[0] is not None:
            return cell_hit
        if len(self._completed_xyz_by_rc) >= 3:
            z, mode = self._interpolate_from_points(self._completed_xyz_by_rc, x, y)
            if z is not None:
                return z, mode
        return None, "none"

    def _interpolate_by_cell(
        self,
        x: float,
        y: float,
        points_by_rc: dict[tuple[int, int], tuple[float, float, float]],
    ) -> tuple[float | None, str]:
        for row_idx in range(self._rows - 1):
            for col_idx in range(self._cols - 1):
                if not self._cell_contains_point(row_idx, col_idx, x, y):
                    continue
                z, mode = self._interpolate_in_cell(
                    row_idx,
                    col_idx,
                    x,
                    y,
                    points_by_rc=points_by_rc,
                    allow_extrapolation=False,
                )
                if z is not None:
                    return z, mode
        return None, "none"

    def _cell_contains_point(self, row_idx: int, col_idx: int, x: float, y: float) -> bool:
        quad = self._cell_quad_xy(row_idx, col_idx)
        if quad is None:
            return False
        point = np.array([float(x), float(y)], dtype=float)
        p00, p10, p11, p01 = quad
        tri_a = np.array([p00, p10, p11], dtype=float)
        tri_b = np.array([p00, p11, p01], dtype=float)
        bary_a = self._barycentric_weights(point, tri_a)
        if bary_a is not None and min(bary_a) >= -1e-9:
            return True
        bary_b = self._barycentric_weights(point, tri_b)
        return bary_b is not None and min(bary_b) >= -1e-9

    def _cell_quad_xy(
        self,
        row_idx: int,
        col_idx: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
        keys = [
            (row_idx, col_idx),
            (row_idx, col_idx + 1),
            (row_idx + 1, col_idx + 1),
            (row_idx + 1, col_idx),
        ]
        if any(key not in self._planned_xy_by_rc for key in keys):
            return None
        return tuple(
            np.array(self._planned_xy_by_rc[key], dtype=float)
            for key in keys
        )

    def _interpolate_in_cell(
        self,
        row_idx: int,
        col_idx: int,
        x: float,
        y: float,
        *,
        points_by_rc: dict[tuple[int, int], tuple[float, float, float]],
        allow_extrapolation: bool,
    ) -> tuple[float | None, str]:
        keys = {
            "p00": (row_idx, col_idx),
            "p10": (row_idx, col_idx + 1),
            "p11": (row_idx + 1, col_idx + 1),
            "p01": (row_idx + 1, col_idx),
        }
        available = {
            name: points_by_rc[key]
            for name, key in keys.items()
            if key in points_by_rc
        }
        if len(available) < 3:
            return None, "none"

        if len(available) == 4:
            quad = self._cell_quad_xy(row_idx, col_idx)
            if quad is None:
                return None, "none"
            uv = self._solve_bilinear_uv(float(x), float(y), *quad)
            if uv is None:
                return None, "none"
            u, v = uv
            z00 = available["p00"][2]
            z10 = available["p10"][2]
            z11 = available["p11"][2]
            z01 = available["p01"][2]
            z = (
                (1.0 - u) * (1.0 - v) * z00
                + u * (1.0 - v) * z10
                + u * v * z11
                + (1.0 - u) * v * z01
            )
            return float(z), "cell-bilinear"

        vertices = np.array(
            [[point[0], point[1], point[2]] for point in available.values()],
            dtype=float,
        )
        point = np.array([float(x), float(y)], dtype=float)
        bary = self._barycentric_weights(point, vertices[:, :2])
        if bary is None:
            return None, "none"
        if not allow_extrapolation and min(bary) < -1e-9:
            return None, "none"
        z = float(np.dot(bary, vertices[:, 2]))
        return z, "cell-triangle"

    def _interpolate_from_points(
        self,
        points_by_rc: dict[tuple[int, int], tuple[float, float, float]],
        x: float,
        y: float,
    ) -> tuple[float | None, str]:
        triangle_hit = self._interpolate_via_triangles(points_by_rc, x, y)
        if triangle_hit[0] is not None:
            return triangle_hit
        return self._interpolate_idw(points_by_rc, x, y)

    def _interpolate_via_triangles(
        self,
        points_by_rc: dict[tuple[int, int], tuple[float, float, float]],
        x: float,
        y: float,
    ) -> tuple[float | None, str]:
        if len(points_by_rc) < 3:
            return None, "none"
        point_items = sorted(points_by_rc.items())
        px = np.array([point[0] for _, point in point_items], dtype=float)
        py = np.array([point[1] for _, point in point_items], dtype=float)
        pz = np.array([point[2] for _, point in point_items], dtype=float)
        tri = Triangulation(px, py)
        point = np.array([float(x), float(y)], dtype=float)
        for a, b, c in np.array(tri.triangles, dtype=int):
            triangle = np.array(
                [
                    [px[a], py[a], pz[a]],
                    [px[b], py[b], pz[b]],
                    [px[c], py[c], pz[c]],
                ],
                dtype=float,
            )
            bary = self._barycentric_weights(point, triangle[:, :2])
            if bary is None:
                continue
            if min(bary) >= -1e-9:
                z = float(np.dot(bary, triangle[:, 2]))
                return z, "triangulated"
        return None, "none"

    def _interpolate_idw(
        self,
        points_by_rc: dict[tuple[int, int], tuple[float, float, float]],
        x: float,
        y: float,
    ) -> tuple[float | None, str]:
        if not points_by_rc:
            return None, "none"
        samples = []
        for point_x, point_y, point_z in points_by_rc.values():
            dist = math.hypot(point_x - x, point_y - y)
            if dist < 1e-9:
                return float(point_z), "measured"
            samples.append((dist, point_z))
        samples.sort(key=lambda item: item[0])
        nearest = samples[: min(4, len(samples))]
        if not nearest:
            return None, "none"
        weights = [1.0 / max(dist * dist, 1e-9) for dist, _ in nearest]
        z = sum(weight * value for weight, (_, value) in zip(weights, nearest)) / sum(weights)
        return float(z), "estimated"

    def _find_prediction(
        self,
        start_row: int,
        start_col: int,
        row_step: int,
        col_step: int,
        used_cells: set[tuple[int, int]],
    ) -> AreaGridCellPrediction | None:
        if row_step > 0:
            row_range = range(start_row, self._rows - 1, row_step)
        else:
            row_range = range(start_row, -1, row_step)

        if col_step > 0:
            col_range = range(start_col, self._cols - 1, col_step)
        else:
            col_range = range(start_col, -1, col_step)

        for row_idx in row_range:
            for col_idx in col_range:
                if (row_idx, col_idx) in used_cells:
                    continue
                prediction = self._predict_cell_center(row_idx, col_idx)
                if prediction is not None:
                    return prediction
        return None

    def _predict_cell_center(self, row_idx: int, col_idx: int) -> AreaGridCellPrediction | None:
        keys = [
            (row_idx, col_idx),
            (row_idx, col_idx + 1),
            (row_idx + 1, col_idx),
            (row_idx + 1, col_idx + 1),
        ]
        available = [self._completed_xyz_by_rc[key] for key in keys if key in self._completed_xyz_by_rc]
        if len(available) < 3:
            return None

        source = f"cell r{row_idx + 1}c{col_idx + 1}"
        center_x = sum(point[0] for point in available) / len(available)
        center_y = sum(point[1] for point in available) / len(available)

        center_z, mode = self._interpolate_in_cell(
            row_idx,
            col_idx,
            center_x,
            center_y,
            points_by_rc=self._completed_xyz_by_rc,
            allow_extrapolation=False,
        )
        if center_z is None:
            center_z = sum(point[2] for point in available) / len(available)
            mode = "averaged"
        return AreaGridCellPrediction(
            row=row_idx,
            col=col_idx,
            source=source,
            interpolation_mode=mode,
            x=float(center_x),
            y=float(center_y),
            z=float(center_z),
        )

    @staticmethod
    def _barycentric_weights(point: np.ndarray, triangle_xy: np.ndarray) -> np.ndarray | None:
        if triangle_xy.shape[0] != 3:
            return None
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

    @staticmethod
    def _solve_bilinear_uv(
        x: float,
        y: float,
        p00: np.ndarray,
        p10: np.ndarray,
        p11: np.ndarray,
        p01: np.ndarray,
    ) -> tuple[float, float] | None:
        u = 0.5
        v = 0.5
        target = np.array([float(x), float(y)], dtype=float)
        for _ in range(12):
            current = (
                (1.0 - u) * (1.0 - v) * p00
                + u * (1.0 - v) * p10
                + u * v * p11
                + (1.0 - u) * v * p01
            )
            error = current - target
            if float(np.linalg.norm(error)) < 1e-6:
                break

            du = (1.0 - v) * (p10 - p00) + v * (p11 - p01)
            dv = (1.0 - u) * (p01 - p00) + u * (p11 - p10)
            jac = np.array([[du[0], dv[0]], [du[1], dv[1]]], dtype=float)
            try:
                step = np.linalg.solve(jac, error)
            except np.linalg.LinAlgError:
                return None
            u -= float(step[0])
            v -= float(step[1])

        if -1e-3 <= u <= 1.0 + 1e-3 and -1e-3 <= v <= 1.0 + 1e-3:
            return float(min(max(u, 0.0), 1.0)), float(min(max(v, 0.0), 1.0))
        return None

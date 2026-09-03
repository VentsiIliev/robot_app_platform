from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, Sequence

import cv2
import numpy as np

from .models import PixelPoint


class MarkerOrientationStrategy(Protocol):
    def estimate(self, corners_px: Sequence[PixelPoint]) -> "MarkerOrientationEstimate": ...


@dataclass(frozen=True)
class MarkerOrientationEstimate:
    primary_deg: float
    samples: tuple[tuple[str, float], ...]
    diagnostics: tuple[tuple[str, float], ...] = ()


class CornerEdgeOrientationStrategy:
    """Image-plane orientation averaged from all four canonical marker edges."""

    def orientation_deg(self, corners_px: Sequence[PixelPoint]) -> float:
        if len(corners_px) != 4:
            raise ValueError("Four marker corners are required for edge orientation")
        # ArUco corners are TL, TR, BR, BL. Convert every directed edge back to
        # the canonical top-edge angle, then circular-average the four values.
        expected_edge_offsets = (0.0, 90.0, 180.0, -90.0)
        edge_angles = []
        for index, expected_offset in enumerate(expected_edge_offsets):
            start = corners_px[index]
            end = corners_px[(index + 1) % 4]
            measured = math.degrees(
                math.atan2(end[1] - start[1], end[0] - start[0])
            )
            edge_angles.append(_normalize_angle_deg(measured - expected_offset))
        radians = [math.radians(angle) for angle in edge_angles]
        angle = math.degrees(
            math.atan2(
                sum(math.sin(value) for value in radians),
                sum(math.cos(value) for value in radians),
            )
        )
        return _normalize_angle_deg(angle)

    def estimate(self, corners_px: Sequence[PixelPoint]) -> MarkerOrientationEstimate:
        angle = self.orientation_deg(corners_px)
        return MarkerOrientationEstimate(angle, (("corner_edge", angle),))


class SolvePnPOrientationStrategy:
    """Camera-frame marker yaw from a square planar PnP solution."""

    def __init__(
        self,
        *,
        marker_size_mm: float,
        camera_matrix: np.ndarray,
        distortion_coefficients: np.ndarray,
    ) -> None:
        if marker_size_mm <= 0.0:
            raise ValueError("marker_size_mm must be positive")
        self._camera_matrix = np.asarray(camera_matrix, dtype=np.float64).reshape(3, 3)
        self._distortion = np.asarray(distortion_coefficients, dtype=np.float64).reshape(-1, 1)
        half = float(marker_size_mm) / 2.0
        self._object_points = np.asarray(
            [
                [-half, +half, 0.0],
                [+half, +half, 0.0],
                [+half, -half, 0.0],
                [-half, -half, 0.0],
            ],
            dtype=np.float64,
        )

    def orientation_deg(self, corners_px: Sequence[PixelPoint]) -> float:
        return self._solve_pose(corners_px)[0]

    def _solve_pose(
        self,
        corners_px: Sequence[PixelPoint],
    ) -> tuple[float, tuple[tuple[str, float], ...]]:
        image_points = np.asarray(corners_px, dtype=np.float64).reshape(4, 2)
        result = cv2.solvePnPGeneric(
            self._object_points,
            image_points,
            self._camera_matrix,
            self._distortion,
            flags=cv2.SOLVEPNP_IPPE_SQUARE,
        )
        success, rotation_vectors, translation_vectors = result[:3]
        if not success or not rotation_vectors:
            raise RuntimeError("IPPE square pose estimation failed")

        candidates = []
        for candidate_index, (rvec, tvec) in enumerate(zip(rotation_vectors, translation_vectors)):
            translation = np.asarray(tvec, dtype=np.float64).reshape(3)
            if translation[2] <= 0.0:
                continue
            projected, _ = cv2.projectPoints(
                self._object_points,
                rvec,
                tvec,
                self._camera_matrix,
                self._distortion,
            )
            error = float(
                np.sqrt(np.mean(np.sum((projected.reshape(4, 2) - image_points) ** 2, axis=1)))
            )
            candidates.append((error, candidate_index, rvec, translation))
        if not candidates:
            raise RuntimeError("IPPE returned no positive-Z marker pose")

        error, selected_index, selected_rvec, translation = min(
            candidates,
            key=lambda item: item[0],
        )
        rotation, _ = cv2.Rodrigues(selected_rvec)
        marker_x_axis = rotation[:, 0]
        yaw = _normalize_angle_deg(
            math.degrees(math.atan2(marker_x_axis[1], marker_x_axis[0]))
        )
        rx, ry, _rz = _rotation_matrix_to_euler_xyz_deg(rotation)
        tilt = math.degrees(
            math.acos(float(np.clip(abs(rotation[2, 2]), 0.0, 1.0)))
        )
        diagnostics = (
            ("solve_pnp.rx_deg", rx),
            ("solve_pnp.ry_deg", ry),
            ("solve_pnp.tilt_deg", tilt),
            ("solve_pnp.z_mm", float(translation[2])),
            ("solve_pnp.reprojection_error_px", error),
            ("solve_pnp.candidate_count", float(len(rotation_vectors))),
            ("solve_pnp.selected_candidate", float(selected_index)),
        )
        return yaw, diagnostics

    def estimate(self, corners_px: Sequence[PixelPoint]) -> MarkerOrientationEstimate:
        angle, diagnostics = self._solve_pose(corners_px)
        return MarkerOrientationEstimate(
            angle,
            (("solve_pnp", angle),),
            diagnostics,
        )


class ComparingOrientationStrategy:
    """Evaluate multiple strategies from the same corners and select one primary."""

    def __init__(
        self,
        strategies: Sequence[MarkerOrientationStrategy],
        *,
        primary_name: str,
    ) -> None:
        if not strategies:
            raise ValueError("At least one orientation strategy is required")
        self._strategies = tuple(strategies)
        self._primary_name = str(primary_name).strip().lower()

    def estimate(self, corners_px: Sequence[PixelPoint]) -> MarkerOrientationEstimate:
        samples = []
        diagnostics = []
        for strategy in self._strategies:
            estimate = strategy.estimate(corners_px)
            samples.extend(estimate.samples)
            diagnostics.extend(estimate.diagnostics)
        values = dict(samples)
        if self._primary_name not in values:
            raise RuntimeError(f"Primary orientation strategy {self._primary_name!r} is absent")
        return MarkerOrientationEstimate(
            values[self._primary_name],
            tuple(samples),
            tuple(diagnostics),
        )


def _normalize_angle_deg(angle: float) -> float:
    return (float(angle) + 180.0) % 360.0 - 180.0


def _rotation_matrix_to_euler_xyz_deg(rotation: np.ndarray) -> tuple[float, float, float]:
    sy = math.hypot(float(rotation[0, 0]), float(rotation[1, 0]))
    if sy > 1e-9:
        rx = math.atan2(float(rotation[2, 1]), float(rotation[2, 2]))
        ry = math.atan2(-float(rotation[2, 0]), sy)
        rz = math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))
    else:
        rx = math.atan2(-float(rotation[1, 2]), float(rotation[1, 1]))
        ry = math.atan2(-float(rotation[2, 0]), sy)
        rz = 0.0
    return tuple(_normalize_angle_deg(math.degrees(value)) for value in (rx, ry, rz))

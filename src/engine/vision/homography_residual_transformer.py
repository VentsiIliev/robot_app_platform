import json
import logging
import os
from typing import Tuple

import numpy as np
from scipy.optimize import minimize

from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.calibration.robot_calibration.metrics import (
    HomographyResidualModel,
    HomographyTPSResidualModel,
    derive_calibration_artifact_paths,
)

_MISSING = object()


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


class HomographyResidualTransformer(ICoordinateTransformer):
    def __init__(
        self,
        matrix_path: str,
        camera_to_tcp_x_offset: float = _MISSING,
        camera_to_tcp_y_offset: float = _MISSING,
    ):
        self._matrix_path = matrix_path
        self._artifact_path = derive_calibration_artifact_paths(matrix_path)["homography_residual_path"]
        self._model: HomographyResidualModel | None = None
        self._logger = logging.getLogger(self.__class__.__name__)
        self._camera_to_tcp_x: float | None = None if camera_to_tcp_x_offset is _MISSING else float(camera_to_tcp_x_offset)
        self._camera_to_tcp_y: float | None = None if camera_to_tcp_y_offset is _MISSING else float(camera_to_tcp_y_offset)
        self._has_camera_to_tcp = (
            (camera_to_tcp_x_offset is not _MISSING) and
            (camera_to_tcp_y_offset is not _MISSING)
        )

        # Explicit simulation-only fallback. Production behavior remains unchanged
        # unless ROBOT_FAKE_VISION_CALIBRATION is deliberately enabled.
        self._fake_mode = _env_flag("ROBOT_FAKE_VISION_CALIBRATION", False)
        self._fake_ppm = float(os.environ.get("ROBOT_FAKE_VISION_PPM", "3.663114"))
        self._fake_center_x = float(os.environ.get("ROBOT_FAKE_VISION_CENTER_X", "640.0"))
        self._fake_center_y = float(os.environ.get("ROBOT_FAKE_VISION_CENTER_Y", "360.0"))
        self._fake_origin_x = float(os.environ.get("ROBOT_FAKE_VISION_ORIGIN_X", "-96.039"))
        self._fake_origin_y = float(os.environ.get("ROBOT_FAKE_VISION_ORIGIN_Y", "560.555"))
        self._fake_x_sign = float(os.environ.get("ROBOT_FAKE_VISION_X_SIGN", "1.0"))
        self._fake_y_sign = float(os.environ.get("ROBOT_FAKE_VISION_Y_SIGN", "-1.0"))

        if self._fake_mode:
            if self._fake_ppm <= 0.0:
                raise ValueError("ROBOT_FAKE_VISION_PPM must be > 0")
            if self._fake_x_sign == 0.0 or self._fake_y_sign == 0.0:
                raise ValueError("ROBOT_FAKE_VISION_X_SIGN and ROBOT_FAKE_VISION_Y_SIGN must be non-zero")
            self._logger.warning(
                "FAKE vision calibration enabled: ppm=%.6f center=(%.3f, %.3f) "
                "origin=(%.3f, %.3f) signs=(%.1f, %.1f)",
                self._fake_ppm,
                self._fake_center_x,
                self._fake_center_y,
                self._fake_origin_x,
                self._fake_origin_y,
                self._fake_x_sign,
                self._fake_y_sign,
            )
        else:
            self._load()

    def _load(self) -> None:
        if self._fake_mode:
            self._model = None
            return
        try:
            with open(self._artifact_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            basis = payload.get("basis", "quadratic_uv")
            if basis == "tps":
                self._model = HomographyTPSResidualModel(
                    homography_matrix=payload["homography_matrix"],
                    support_points=payload["support_points"],
                    dx_residuals=payload["dx_residuals"],
                    dy_residuals=payload["dy_residuals"],
                )
            else:
                self._model = HomographyResidualModel(
                    homography_matrix=np.asarray(payload.get("homography_matrix", []), dtype=np.float64).reshape(3, 3),
                    dx_coeffs=np.asarray(payload.get("dx_coeffs", []), dtype=np.float64).reshape(-1),
                    dy_coeffs=np.asarray(payload.get("dy_coeffs", []), dtype=np.float64).reshape(-1),
                )
            self._logger.info("Homography residual model loaded (basis=%s) from %s", basis, self._artifact_path)
        except Exception as exc:
            self._logger.warning(
                "Homography residual model not available at %s: %s",
                self._artifact_path,
                exc,
            )
            self._model = None

    def is_available(self) -> bool:
        return self._fake_mode or self._model is not None

    def reload(self) -> bool:
        if self._fake_mode:
            return True
        self._load()
        return self.is_available()

    def _fake_transform(self, x: float, y: float) -> Tuple[float, float]:
        dx_mm = (float(x) - self._fake_center_x) / self._fake_ppm
        dy_mm = (float(y) - self._fake_center_y) / self._fake_ppm
        return (
            self._fake_origin_x + self._fake_x_sign * dx_mm,
            self._fake_origin_y + self._fake_y_sign * dy_mm,
        )

    def _fake_inverse_transform(self, x: float, y: float) -> Tuple[float, float]:
        px = self._fake_center_x + (
            (float(x) - self._fake_origin_x) / self._fake_x_sign
        ) * self._fake_ppm
        py = self._fake_center_y + (
            (float(y) - self._fake_origin_y) / self._fake_y_sign
        ) * self._fake_ppm
        return float(px), float(py)

    def transform(self, x: float, y: float) -> Tuple[float, float]:
        if self._fake_mode:
            return self._fake_transform(x, y)
        if self._model is None:
            raise RuntimeError("Homography residual model not loaded")
        robot_pt = self._model.predict([float(x), float(y)])
        return float(robot_pt[0]), float(robot_pt[1])

    def transform_to_tcp(self, x: float, y: float) -> Tuple[float, float]:
        if not self._has_camera_to_tcp:
            raise RuntimeError(
                "Camera-to-TCP offsets were not provided at construction — "
                "pass camera_to_tcp_x_offset and camera_to_tcp_y_offset to HomographyResidualTransformer"
            )
        cx, cy = self.transform(x, y)
        return cx + self._camera_to_tcp_x, cy + self._camera_to_tcp_y

    def inverse_transform(self, x: float, y: float) -> Tuple[float, float]:
        if self._fake_mode:
            return self._fake_inverse_transform(x, y)
        if self._model is None:
            raise RuntimeError("Homography residual model not loaded")
        # Initial guess: pure homography inverse (cheap, usually within 1-2 px of true answer)
        H_inv = np.linalg.inv(np.asarray(self._model.homography_matrix, dtype=np.float64))
        robot_h = np.array([float(x), float(y), 1.0], dtype=np.float64)
        cam_h = H_inv @ robot_h
        cam_init = (cam_h[:2] / cam_h[2]).astype(np.float64)
        # Refine: find cam_xy such that predict(cam_xy) == (x, y)
        target = np.array([float(x), float(y)], dtype=np.float64)

        def _sq_error(cam_xy):
            diff = self._model.predict(cam_xy) - target
            return float(diff @ diff)

        result = minimize(_sq_error, cam_init, method="L-BFGS-B", options={"ftol": 1e-14, "gtol": 1e-9})
        return float(result.x[0]), float(result.x[1])

    def inverse_transform_points(self, robot_xy_points) -> np.ndarray:
        """Batch inverse for dense editor previews without one optimizer per point."""
        targets = np.asarray(robot_xy_points, dtype=np.float64).reshape(-1, 2)
        if len(targets) == 0:
            return np.empty((0, 2), dtype=np.float64)
        if self._fake_mode:
            return np.asarray([self._fake_inverse_transform(x, y) for x, y in targets], dtype=float)
        if self._model is None:
            raise RuntimeError("Homography residual model not loaded")

        h_inv = np.linalg.inv(np.asarray(self._model.homography_matrix, dtype=np.float64))
        homogeneous = np.column_stack([targets, np.ones(len(targets), dtype=float)])
        initial = homogeneous @ h_inv.T
        camera = initial[:, :2] / initial[:, 2:3]

        def predict_many(points: np.ndarray) -> np.ndarray:
            return np.asarray([self._model.predict(point) for point in points], dtype=np.float64)

        # Independent damped Newton updates, vectorized across the entire contour.
        epsilon_px = 0.05
        for _ in range(8):
            prediction = predict_many(camera)
            error = prediction - targets
            if float(np.max(np.linalg.norm(error, axis=1))) <= 1e-7:
                break
            shifted_x = camera.copy()
            shifted_y = camera.copy()
            shifted_x[:, 0] += epsilon_px
            shifted_y[:, 1] += epsilon_px
            jac_x = (predict_many(shifted_x) - prediction) / epsilon_px
            jac_y = (predict_many(shifted_y) - prediction) / epsilon_px
            determinant = jac_x[:, 0] * jac_y[:, 1] - jac_y[:, 0] * jac_x[:, 1]
            valid = np.abs(determinant) > 1e-12
            delta = np.zeros_like(camera)
            delta[valid, 0] = (
                jac_y[valid, 1] * error[valid, 0] - jac_y[valid, 0] * error[valid, 1]
            ) / determinant[valid]
            delta[valid, 1] = (
                -jac_x[valid, 1] * error[valid, 0] + jac_x[valid, 0] * error[valid, 1]
            ) / determinant[valid]
            camera[valid] -= np.clip(delta[valid], -5.0, 5.0)
        return camera

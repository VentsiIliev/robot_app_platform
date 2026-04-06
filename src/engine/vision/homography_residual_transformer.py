import json
import logging
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
        self._load()

    def _load(self) -> None:
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
        return self._model is not None

    def reload(self) -> bool:
        self._load()
        return self.is_available()

    def transform(self, x: float, y: float) -> Tuple[float, float]:
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

from __future__ import annotations

import numpy as np

from src.engine.robot.path_preparation.pixel_to_mm.context import PixelToMmContext
from src.engine.robot.targeting import VisionPoseRequest


class HomographyResidualStrategy:
    """Resolve every pixel point through the calibrated resolver model."""

    def convert(
        self,
        compensated_pts_px: np.ndarray,
        *,
        resolver,
        context: PixelToMmContext,
    ) -> tuple[list, list[tuple[float, float]]]:
        target_point = resolver.registry.by_name(context.target_point_name)
        seeded_results = [
            resolver.resolve(
                VisionPoseRequest(
                    float(px),
                    float(py),
                    z_mm=context.base_z,
                    rz_degrees=context.rz_offset,
                    rx_degrees=context.rx,
                    ry_degrees=context.ry,
                ),
                target_point,
                frame=context.calibration_frame_name,
            )
            for px, py in compensated_pts_px
        ]
        robot_xy_points = [
            (float(result.final_xy[0]), float(result.final_xy[1]))
            for result in seeded_results
        ]
        context.logger.info(
            "[EXECUTE] Pixel-to-mm transform: mode=%s points=%d target=%s frame=%s",
            context.mode_name,
            len(robot_xy_points),
            context.target_point_name,
            context.calibration_frame_name,
        )
        return seeded_results, robot_xy_points

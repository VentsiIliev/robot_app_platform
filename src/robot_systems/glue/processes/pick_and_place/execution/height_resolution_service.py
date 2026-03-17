from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.engine.robot.height_measuring.i_height_measuring_service import IHeightMeasuringService
from src.robot_systems.glue.processes.pick_and_place.config import PickAndPlaceConfig
from src.robot_systems.glue.processes.pick_and_place.errors import (
    PickAndPlaceErrorCode,
    PickAndPlaceErrorInfo,
    PickAndPlaceStage,
)


@dataclass(frozen=True)
class HeightResolutionResult:
    value_mm: Optional[float]
    source: str
    error: Optional[PickAndPlaceErrorInfo] = None


class HeightResolutionService:
    def __init__(
        self,
        config: PickAndPlaceConfig,
        height_service: Optional[IHeightMeasuringService],
        logger: logging.Logger,
    ) -> None:
        self._config = config
        self._height_service = height_service
        self._logger = logger

    def resolve(self, fallback_height_mm: float, robot_x: float, robot_y: float) -> HeightResolutionResult:
        source = (self._config.height_source or "zero").lower()

        if source == "measured":
            if self._height_service is None:
                return HeightResolutionResult(
                    value_mm=None,
                    source=source,
                    error=PickAndPlaceErrorInfo(
                        code=PickAndPlaceErrorCode.HEIGHT_MEASUREMENT_FAILED,
                        stage=PickAndPlaceStage.HEIGHT,
                        message="Height measurement service is not available",
                    ),
                )
            try:
                measured_z = self._height_service.measure_at(robot_x, robot_y)
            except Exception as exc:
                self._logger.exception("Height measurement failed")
                return HeightResolutionResult(
                    value_mm=None,
                    source=source,
                    error=PickAndPlaceErrorInfo(
                        code=PickAndPlaceErrorCode.HEIGHT_MEASUREMENT_FAILED,
                        stage=PickAndPlaceStage.HEIGHT,
                        message="Height measurement failed",
                        detail=str(exc),
                    ),
                )
            if measured_z is None:
                return HeightResolutionResult(
                    value_mm=None,
                    source=source,
                    error=PickAndPlaceErrorInfo(
                        code=PickAndPlaceErrorCode.HEIGHT_MEASUREMENT_FAILED,
                        stage=PickAndPlaceStage.HEIGHT,
                        message="Height measurement returned no value",
                    ),
                )
            self._logger.debug("Measured z(wp height) -> %s", measured_z)
            return HeightResolutionResult(
                value_mm=measured_z + self._config.height_adjustment_mm,
                source=source,
            )

        if source == "workpiece":
            self._logger.debug("Using workpiece height -> %s", fallback_height_mm)
            return HeightResolutionResult(value_mm=fallback_height_mm, source=source)

        self._logger.debug("Height source 'zero' -> %s", 0)
        return HeightResolutionResult(
            value_mm=0 + self._config.height_adjustment_mm,
            source="zero",
        )

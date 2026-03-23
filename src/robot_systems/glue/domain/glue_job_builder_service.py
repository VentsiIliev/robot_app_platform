from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.robot_systems.glue.targeting import VisionPoseRequest, VisionTargetResolver


class GlueJobBuildError(ValueError):
    pass


@dataclass(frozen=True)
class GlueJobSegment:
    workpiece_id: str
    pattern_type: str
    segment_index: int
    points: list[list[float]]
    image_points: list[tuple[float, float]]
    settings: dict[str, Any]


@dataclass(frozen=True)
class GlueJob:
    segments: list[GlueJobSegment]

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def workpiece_count(self) -> int:
        return len({segment.workpiece_id for segment in self.segments})


class GlueJobBuilderService:
    _PATTERN_ORDER = ("Contour", "Fill")
    _RX = 180.0
    _RY = 0.0

    def __init__(
        self,
        transformer: ICoordinateTransformer | None = None,
        resolver: VisionTargetResolver | None = None,
        z_min: float = 0.0,
    ) -> None:
        self._transformer = transformer
        self._resolver = resolver
        self._z_min = float(z_min)

    def build_job(self, matched_workpieces: list[dict[str, Any]]) -> GlueJob:
        segments: list[GlueJobSegment] = []
        for workpiece in matched_workpieces:
            workpiece_id = self._get_workpiece_id(workpiece)
            spray_pattern = self._get_spray_pattern(workpiece)
            for pattern_type in self._PATTERN_ORDER:
                for segment_index, raw_segment in enumerate(spray_pattern.get(pattern_type, [])):
                    settings = self._extract_settings(raw_segment)
                    points = self._extract_points(raw_segment, settings)
                    segments.append(
                        GlueJobSegment(
                            workpiece_id=workpiece_id,
                            pattern_type=pattern_type,
                            segment_index=segment_index,
                            points=points,
                            image_points=self._extract_image_points(raw_segment),
                            settings=settings,
                        )
                    )
        return GlueJob(segments=segments)

    def to_process_paths(self, job: GlueJob) -> list[tuple[list[list[float]], dict[str, Any], dict[str, Any]]]:
        return [
            (
                list(segment.points),
                dict(segment.settings),
                {
                    "workpiece_id": segment.workpiece_id,
                    "pattern_type": segment.pattern_type,
                    "segment_index": segment.segment_index,
                },
            )
            for segment in job.segments
        ]

    def _extract_points(self, raw_segment: dict[str, Any], settings: dict[str, Any]) -> list[list[float]]:
        raw_points = raw_segment.get("contour")
        if raw_points is None:
            raw_points = []
        points: list[list[float]] = []
        base_z = self._z_min + self._safe_float(settings.get("spraying_height"), 0.0)
        rz = self._safe_float(settings.get("rz_angle"), 0.0)

        for raw_point in raw_points:
            point = raw_point
            while self._is_singleton_container(point):
                point = point[0]
            if not self._is_coordinate_pair(point):
                continue

            px, py = float(point[0]), float(point[1])

            if self._resolver is not None:
                result = self._resolver.resolve(
                    VisionPoseRequest(px, py, z_mm=base_z, rz_degrees=rz, rx_degrees=self._RX, ry_degrees=self._RY),
                    self._resolver.registry.tool(),
                    # frame=TargetFrame.CALIBRATION,  # or PICKUP, etc.
                )
                x, y, z, _, _, final_rz = result.robot_pose()
            else:
                raise GlueJobBuildError("Robot coordinate transformer is unavailable")

            points.append([x, y, z, self._RX, self._RY, final_rz])

        if not points:
            raise GlueJobBuildError("Spray segment contour is empty")
        return points

    def _extract_settings(self, raw_segment: dict[str, Any]) -> dict[str, Any]:
        raw_settings = raw_segment.get("settings")
        settings = dict(raw_settings) if raw_settings is not None else {}
        if not settings:
            raise GlueJobBuildError("Spray segment settings are missing")
        return settings

    def _extract_image_points(self, raw_segment: dict[str, Any]) -> list[tuple[float, float]]:
        raw_points = raw_segment.get("contour")
        if raw_points is None:
            raw_points = []
        points: list[tuple[float, float]] = []
        for raw_point in raw_points:
            point = raw_point
            while self._is_singleton_container(point):
                point = point[0]
            if not self._is_coordinate_pair(point):
                continue
            points.append((float(point[0]), float(point[1])))
        return points

    def _get_workpiece_id(self, workpiece: Any) -> str:
        if isinstance(workpiece, dict):
            return str(workpiece.get("workpieceId") or workpiece.get("name") or "")
        return str(getattr(workpiece, "workpieceId", "") or getattr(workpiece, "name", "") or "")

    def _get_spray_pattern(self, workpiece: Any) -> dict[str, Any]:
        if isinstance(workpiece, dict):
            result = workpiece.get("sprayPattern")
        else:
            result = getattr(workpiece, "sprayPattern", None)
        return result if result is not None else {}

    def _is_singleton_container(self, value: Any) -> bool:
        if isinstance(value, (str, bytes)):
            return False
        try:
            return len(value) == 1
        except Exception:
            return False

    def _is_coordinate_pair(self, value: Any) -> bool:
        if isinstance(value, (str, bytes)):
            return False
        try:
            return len(value) >= 2
        except Exception:
            return False

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            return float(str(value).replace(",", "")) if value is not None else default
        except (ValueError, TypeError):
            return default

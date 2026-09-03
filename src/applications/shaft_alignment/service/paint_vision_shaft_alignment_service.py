from __future__ import annotations

import logging
import json
import os
import statistics
import threading
import time
from collections import deque
from dataclasses import replace
from pathlib import Path
from typing import Callable

import numpy as np

from scripts.paint_shaft_alignment.alignment_reference import (
    AlignmentReference,
    AlignmentReferenceCapture,
)
from scripts.paint_shaft_alignment.coordinate_mapper import (
    CapturePoseCompensatedTransformer,
    MarkerCenterRobotMapper,
    MarkerPlanarSize,
    MarkerRobotPosition,
    TcpCoordinateTransformer,
)
from scripts.paint_shaft_alignment.detector import ShaftMarkerDetector
from scripts.paint_shaft_alignment.models import MarkerDetectionStatus, ShaftMarkerConfig
from scripts.paint_shaft_alignment.orientation_factory import build_orientation_strategy
from scripts.paint_shaft_alignment.paint_vision_factory import (
    build_paint_tcp_transformer,
    build_paint_vision_service,
)
from scripts.paint_shaft_alignment.region import (
    CenteredDetectionRegionProvider,
    PixelRegion,
)
from scripts.paint_shaft_alignment.stabilizer import MarkerSampleStabilizer
from scripts.paint_shaft_alignment.tracker import MarkerRegionTracker
from src.applications.shaft_alignment.service.i_shaft_alignment_service import (
    AlignmentSnapshot,
    AlignmentThresholds,
    IShaftAlignmentService,
)
from src.applications.shaft_alignment.settings.shaft_alignment_settings import ShaftAlignmentSettings


class _NormalizedRegionProvider:
    def __init__(self, fallback) -> None:
        self._fallback = fallback
        self._normalized: tuple[float, float, float, float] | None = None
        self._lock = threading.RLock()

    def set(self, left: float, top: float, right: float, bottom: float) -> None:
        values = tuple(min(1.0, max(0.0, float(value))) for value in (left, top, right, bottom))
        x1, x2 = sorted((values[0], values[2]))
        y1, y2 = sorted((values[1], values[3]))
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Detection region must have positive width and height")
        with self._lock:
            self._normalized = (x1, y1, x2, y2)

    def clear(self) -> None:
        with self._lock:
            self._normalized = None

    @property
    def normalized(self) -> tuple[float, float, float, float] | None:
        with self._lock:
            return self._normalized

    def resolve(self, image_width: int, image_height: int) -> PixelRegion:
        with self._lock:
            normalized = self._normalized
        if normalized is None:
            return self._fallback.resolve(image_width, image_height)
        left, top, right, bottom = normalized
        x1 = min(image_width - 1, max(0, round(left * image_width)))
        y1 = min(image_height - 1, max(0, round(top * image_height)))
        x2 = min(image_width, max(x1 + 1, round(right * image_width)))
        y2 = min(image_height, max(y1 + 1, round(bottom * image_height)))
        return PixelRegion(x1, y1, x2 - x1, y2 - y1)


class PaintVisionShaftAlignmentService(IShaftAlignmentService):
    """Real example backend composed from the same Paint vision stack as the CLI."""

    def __init__(
        self,
        settings_path: str | os.PathLike | None = None,
        *,
        vision_service=None,
        robot_pose_provider: Callable[
            [], list[float] | tuple[float, ...] | None
        ] | None = None,
        work_area_region_provider: Callable[[str], object] | None = None,
    ) -> None:
        self._settings_path = Path(settings_path) if settings_path is not None else (
            Path(__file__).resolve().parents[1] / "settings" / "config.json"
        )
        config = self._load_settings()
        self._config = config
        self._stored_settings = config
        self._logger = logging.getLogger(self.__class__.__name__)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._pending_settings: ShaftAlignmentSettings | None = None
        self._robot_pose_provider = robot_pose_provider
        self._work_area_region_provider = work_area_region_provider
        self._last_pose_error_log_s = 0.0
        self._owns_vision_service = vision_service is None
        self._snapshot = AlignmentSnapshot(message="Detection stopped")
        self._vision = vision_service or build_paint_vision_service(config.active_work_area)
        self._vision.update_settings({"Aruco": {"Enable detection": True}})
        self._configure_runtime(config)
        self._snapshot = AlignmentSnapshot(
            detection_region_normalized=self._base_region.normalized,
            reference_marker_corners_normalized=(
                config.reference_marker_corners_normalized or ()
            ),
            reference_available=self._reference_capture.reference is not None,
            message="Detection stopped",
            **self._reference_snapshot_values(),
        )

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._apply_pending_settings()
            self._stop_event.clear()
            if self._owns_vision_service:
                self._vision.start()
            self._thread = threading.Thread(
                target=self._run,
                name="shaft-alignment-acquisition",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        if self._owns_vision_service:
            self._vision.stop()
        with self._lock:
            self._thread = None
            self._snapshot = AlignmentSnapshot(
                frame=self._snapshot.frame,
                detection_region_normalized=self._base_region.normalized,
                reference_marker_corners_normalized=(
                    self._config.reference_marker_corners_normalized or ()
                ),
                reference_available=self._reference_capture.reference is not None,
                message="Detection stopped",
                **self._reference_snapshot_values(),
            )

    def get_snapshot(self) -> AlignmentSnapshot:
        with self._lock:
            return self._snapshot

    def capture_reference(self, sample_count: int) -> None:
        with self._lock:
            self._reference_capture.start(sample_count)
            self._reference_corner_samples.clear()
            self._reference_point_samples.clear()
            self._check_samples.clear()
            self._persist_runtime_state(
                reference_tcp_x_mm=None,
                reference_tcp_y_mm=None,
                reference_orientation_deg=None,
                reference_marker_width_mm=None,
                reference_marker_height_mm=None,
                reference_marker_corners_normalized=None,
                reference_point_of_interest_normalized=None,
            )
            self._snapshot = replace(
                self._snapshot,
                reference_marker_corners_normalized=(),
                point_of_interest_normalized=None,
                reference_capturing=True,
                reference_samples=0,
                reference_samples_required=self._reference_capture.required_samples,
                reference_available=False,
                reference_tcp_x_mm=None,
                reference_tcp_y_mm=None,
                reference_orientation_deg=None,
                reference_marker_width_mm=None,
                reference_marker_height_mm=None,
            )

    def set_thresholds(self, thresholds: AlignmentThresholds) -> None:
        with self._lock:
            changes = {
                "misalignment_dx_threshold_mm": thresholds.dx_mm,
                "misalignment_dy_threshold_mm": thresholds.dy_mm,
                "misalignment_drz_threshold_deg": thresholds.drz_deg,
                "misalignment_dw_threshold_mm": thresholds.dw_mm,
                "misalignment_dh_threshold_mm": thresholds.dh_mm,
            }
            if any(
                getattr(self._stored_settings, name) != value
                for name, value in changes.items()
            ):
                self._persist_runtime_state(**changes)
            self._thresholds = thresholds

    def get_settings(self) -> ShaftAlignmentSettings:
        with self._lock:
            return self._stored_settings

    def save_settings(self, settings: ShaftAlignmentSettings) -> None:
        settings.validate()
        with self._lock:
            self._write_settings_file(settings)
            self._stored_settings = settings
            self._pending_settings = settings
            self._thresholds = AlignmentThresholds(
                settings.misalignment_dx_threshold_mm,
                settings.misalignment_dy_threshold_mm,
                settings.misalignment_drz_threshold_deg,
                settings.misalignment_dw_threshold_mm,
                settings.misalignment_dh_threshold_mm,
            )

    def check_alignment(self) -> bool:
        with self._lock:
            snapshot = self._snapshot
            required = self._config.alignment_check_samples
            if not (
                snapshot.running
                and snapshot.reference_available
                and snapshot.detected
                and len(self._check_samples) >= required
            ):
                return False
            medians = tuple(
                statistics.median(sample[index] for sample in self._check_samples)
                for index in range(5)
            )
            limits = (
                self._thresholds.dx_mm,
                self._thresholds.dy_mm,
                self._thresholds.drz_deg,
                self._thresholds.dw_mm,
                self._thresholds.dh_mm,
            )
            return all(abs(value) <= limit for value, limit in zip(medians, limits))

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._process_frame()
            except Exception as exc:
                self._logger.exception("Paint shaft alignment acquisition failed")
                with self._lock:
                    self._snapshot = AlignmentSnapshot(running=True, message=str(exc))
            self._stop_event.wait(max(0.0, self._config.detection_interval_s))

    def _process_frame(self) -> None:
        self._apply_pending_settings()
        self._update_capture_pose()
        frame = (
            self._vision.get_latest_raw_frame()
            if self._config.raw_mode
            else self._vision.get_latest_frame()
        )
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            with self._lock:
                self._snapshot = AlignmentSnapshot(
                    running=True,
                    detection_region_normalized=self._base_region.normalized,
                    reference_capturing=self._reference_capture.capturing,
                    reference_samples=self._reference_capture.sample_count,
                    reference_samples_required=self._reference_capture.required_samples,
                    reference_available=self._reference_capture.reference is not None,
                    reference_marker_corners_normalized=(
                        self._config.reference_marker_corners_normalized or ()
                    ),
                    message="Waiting for camera frame",
                    **self._reference_snapshot_values(),
                )
            return
        height, width = frame.shape[:2]
        detection_region = self._load_work_area_detection_region(width, height)
        if detection_region is None:
            with self._lock:
                self._reset_tracking()
                self._check_samples.clear()
                self._snapshot = AlignmentSnapshot(
                    frame=frame.copy(),
                    running=True,
                    detection_region_normalized=None,
                    configuration_warning=True,
                    reference_available=self._reference_capture.reference is not None,
                    reference_marker_corners_normalized=(
                        self._config.reference_marker_corners_normalized or ()
                    ),
                    message=(
                        "Detection region is not defined for work area "
                        f"'{self._config.active_work_area}'. Configure it in Work Area Settings."
                    ),
                    **self._reference_snapshot_values(),
                )
            return
        with self._lock:
            region = self._base_region.resolve(width, height)
        result = self._detector.detect(frame, detection_region=region)
        planar_size = MarkerPlanarSize(False, self._config.marker_size_mm)
        stable = self._stabilizer.estimate()
        target = None
        with self._lock:
            if result.detected:
                target = next(marker for marker in result.detected_markers if marker.marker_id == self._config.marker_id)
                accepted = self._tracker.record_detection(target)
                if not accepted:
                    self._tracker.record_miss()
                stable = self._stabilizer.record_detection(target)
                planar_size = self._mapper.measure_planar_size(target.corners_px, self._config.marker_size_mm)
                sample_position = self._mapper.map_center(target.center_px)
                if (
                    accepted
                    and sample_position.available
                    and planar_size.available
                    and self._reference_capture.capturing
                ):
                    self._reference_corner_samples.append(
                        tuple((x / width, y / height) for x, y in target.corners_px)
                    )
                    self._reference_point_samples.append(
                        self._point_of_interest_for_corners(
                            target.corners_px, width, height
                        )
                    )
                    completed = self._reference_capture.record(
                        sample_position.x_mm,
                        sample_position.y_mm,
                        target.orientation_deg,
                        planar_size.width_mm,
                        planar_size.height_mm,
                    )
                    if completed:
                        self._persist_reference(
                            self._reference_capture.reference,
                            self._median_reference_corners(),
                            self._median_reference_point(),
                        )
                elif accepted and sample_position.available and planar_size.available:
                    sample_misalignment = self._reference_capture.compare(
                        sample_position.x_mm,
                        sample_position.y_mm,
                        target.orientation_deg,
                        planar_size.width_mm,
                        planar_size.height_mm,
                    )
                    if sample_misalignment.available:
                        self._check_samples.append(
                            (
                                sample_misalignment.dx_mm,
                                sample_misalignment.dy_mm,
                                sample_misalignment.orientation_difference_deg,
                                sample_misalignment.marker_width_difference_mm,
                                sample_misalignment.marker_height_difference_mm,
                            )
                        )
                else:
                    self._check_samples.clear()
            elif result.status is MarkerDetectionStatus.MARKER_NOT_FOUND:
                self._tracker.record_miss()
                stable = self._stabilizer.record_miss()
                self._check_samples.clear()

            position = (
                self._mapper.map_center(stable.center_px)
                if stable.stable and stable.center_px is not None
                else MarkerRobotPosition(False, message=stable.message)
            )
            misalignment = None
            if (
                position.available
                and stable.orientation_deg is not None
                and planar_size.available
                and not self._reference_capture.capturing
            ):
                misalignment = self._reference_capture.compare(
                    position.x_mm,
                    position.y_mm,
                    stable.orientation_deg,
                    planar_size.width_mm,
                    planar_size.height_mm,
                )
            exceeded = self._exceeded_limits(misalignment)
            corners = (
                tuple((x / width, y / height) for x, y in target.corners_px)
                if target is not None else ()
            )
            reference = self._reference_capture.reference
            self._snapshot = AlignmentSnapshot(
                frame=frame.copy(),
                running=True,
                detected=result.detected,
                marker_id=result.marker_id,
                marker_corners_normalized=corners,
                detection_region_normalized=self._base_region.normalized,
                reference_marker_corners_normalized=(
                    self._config.reference_marker_corners_normalized or ()
                ),
                tcp_x_mm=position.x_mm,
                tcp_y_mm=position.y_mm,
                orientation_deg=stable.orientation_deg,
                marker_width_mm=planar_size.width_mm,
                marker_height_mm=planar_size.height_mm,
                dx_mm=misalignment.dx_mm if misalignment and misalignment.available else None,
                dy_mm=misalignment.dy_mm if misalignment and misalignment.available else None,
                drz_deg=misalignment.orientation_difference_deg if misalignment and misalignment.available else None,
                dw_mm=misalignment.marker_width_difference_mm if misalignment and misalignment.available else None,
                dh_mm=misalignment.marker_height_difference_mm if misalignment and misalignment.available else None,
                reference_capturing=self._reference_capture.capturing,
                reference_samples=self._reference_capture.sample_count,
                reference_samples_required=self._reference_capture.required_samples,
                reference_available=reference is not None,
                misaligned=bool(exceeded),
                exceeded_limits=exceeded,
                message=result.message,
                **self._reference_snapshot_values(),
            )

    def _exceeded_limits(self, misalignment) -> tuple[str, ...]:
        if misalignment is None or not misalignment.available:
            return ()
        values = (
            ("dX", misalignment.dx_mm, self._thresholds.dx_mm),
            ("dY", misalignment.dy_mm, self._thresholds.dy_mm),
            ("dRZ", misalignment.orientation_difference_deg, self._thresholds.drz_deg),
            ("dW", misalignment.marker_width_difference_mm, self._thresholds.dw_mm),
            ("dH", misalignment.marker_height_difference_mm, self._thresholds.dh_mm),
        )
        return tuple(name for name, value, limit in values if value is not None and abs(value) > limit)

    def _reset_tracking(self) -> None:
        self._tracker.reset()
        self._stabilizer.reset()

    def _apply_pending_settings(self) -> None:
        with self._lock:
            settings = self._pending_settings
            if settings is None:
                return
            self._pending_settings = None
            self._configure_runtime(settings)
            self._snapshot = AlignmentSnapshot(
                frame=self._snapshot.frame,
                running=self._thread is not None,
                detection_region_normalized=self._base_region.normalized,
                reference_marker_corners_normalized=(
                    self._config.reference_marker_corners_normalized or ()
                ),
                reference_available=self._reference_capture.reference is not None,
                message="Settings applied",
                **self._reference_snapshot_values(),
            )

    def _configure_runtime(self, config: ShaftAlignmentSettings) -> None:
        self._config = config
        self._vision.set_raw_mode(config.raw_mode)
        if self._owns_vision_service:
            self._vision.set_active_work_area(config.active_work_area or None)
        self._thresholds = AlignmentThresholds(
            config.misalignment_dx_threshold_mm,
            config.misalignment_dy_threshold_mm,
            config.misalignment_drz_threshold_deg,
            config.misalignment_dw_threshold_mm,
            config.misalignment_dh_threshold_mm,
        )
        self._reference_capture = AlignmentReferenceCapture(config.reference_capture_samples)
        self._reference_corner_samples: list[
            tuple[tuple[float, float], ...]
        ] = []
        self._reference_point_samples: list[tuple[float, float]] = []
        self._check_samples = deque(maxlen=config.alignment_check_samples)
        if config.reference_tcp_x_mm is not None:
            self._reference_capture.restore(
                AlignmentReference(
                    config.reference_tcp_x_mm,
                    config.reference_tcp_y_mm,
                    config.reference_orientation_deg,
                    config.reference_marker_width_mm,
                    config.reference_marker_height_mm,
                )
            )
        marker_config = ShaftMarkerConfig(config.marker_id, config.minimum_area_px2)
        self._detector = ShaftMarkerDetector(
            self._vision,
            marker_config,
            orientation_strategy=build_orientation_strategy(self._vision, config),
        )
        compensated = CapturePoseCompensatedTransformer(
            TcpCoordinateTransformer(build_paint_tcp_transformer(self._vision)),
            config.calibration_pose,
            config.capture_pose,
        )
        self._pose_compensated_transformer = compensated
        if self._robot_pose_provider is not None:
            compensated.clear_capture_pose()
        self._mapper = MarkerCenterRobotMapper(compensated)
        self._base_region = _NormalizedRegionProvider(
            CenteredDetectionRegionProvider(
                config.base_region_width_px,
                config.base_region_height_px,
            )
        )
        self._tracker = MarkerRegionTracker(
            self._base_region,
            padding_px=config.tracking_region_padding_px,
            minimum_width_px=config.tracking_region_minimum_width_px,
            minimum_height_px=config.tracking_region_minimum_height_px,
            recovery_expansion_px=config.tracking_recovery_expansion_px,
            misses_before_fallback=config.marker_misses_before_region_fallback,
            detections_before_tracking=config.detections_before_tracking,
            acquisition_misses_before_reset=config.acquisition_misses_before_reset,
            position_filter_alpha=config.tracking_position_filter_alpha,
            prediction_gain=config.tracking_prediction_gain,
            maximum_center_jump_px=config.tracking_maximum_center_jump_px,
            maximum_area_ratio_change=config.tracking_maximum_area_ratio_change,
        )
        self._stabilizer = MarkerSampleStabilizer(
            required_samples=config.stability_required_samples,
            maximum_center_spread_px=config.stability_maximum_center_spread_px,
            maximum_orientation_spread_deg=config.stability_maximum_orientation_spread_deg,
            misses_before_reset=config.stability_misses_before_reset,
        )

    def _load_settings(self) -> ShaftAlignmentSettings:
        try:
            payload = json.loads(self._settings_path.read_text(encoding="utf-8"))
            return ShaftAlignmentSettings.from_dict(payload)
        except FileNotFoundError:
            return ShaftAlignmentSettings()

    def _persist_reference(
        self,
        reference: AlignmentReference | None,
        corners: tuple[tuple[float, float], ...] | None,
        point_of_interest: tuple[float, float] | None,
    ) -> None:
        if reference is None:
            return
        self._persist_runtime_state(
            reference_tcp_x_mm=reference.x_mm,
            reference_tcp_y_mm=reference.y_mm,
            reference_orientation_deg=reference.orientation_deg,
            reference_marker_width_mm=reference.marker_width_mm,
            reference_marker_height_mm=reference.marker_height_mm,
            reference_marker_corners_normalized=corners,
            reference_point_of_interest_normalized=point_of_interest,
        )

    def _median_reference_corners(self) -> tuple[tuple[float, float], ...] | None:
        if not self._reference_corner_samples:
            return None
        return tuple(
            (
                statistics.median(sample[index][0] for sample in self._reference_corner_samples),
                statistics.median(sample[index][1] for sample in self._reference_corner_samples),
            )
            for index in range(4)
        )

    def _median_reference_point(self) -> tuple[float, float] | None:
        if not self._reference_point_samples:
            return None
        return (
            statistics.median(point[0] for point in self._reference_point_samples),
            statistics.median(point[1] for point in self._reference_point_samples),
        )

    def _point_of_interest_for_corners(
        self,
        corners: tuple[tuple[float, float], ...],
        image_width: int,
        image_height: int,
    ) -> tuple[float, float]:
        points = np.asarray(corners, dtype=float)
        center = points.mean(axis=0)
        horizontal = ((points[1] - points[0]) + (points[2] - points[3])) / 2.0
        vertical = ((points[3] - points[0]) + (points[2] - points[1])) / 2.0
        point = (
            center
            + horizontal
            * (self._config.point_of_interest_x_offset_mm / self._config.marker_size_mm)
            + vertical
            * (self._config.point_of_interest_y_offset_mm / self._config.marker_size_mm)
        )
        return float(point[0] / image_width), float(point[1] / image_height)

    def _reference_snapshot_values(self) -> dict[str, object]:
        return {
            "reference_tcp_x_mm": self._config.reference_tcp_x_mm,
            "reference_tcp_y_mm": self._config.reference_tcp_y_mm,
            "reference_orientation_deg": self._config.reference_orientation_deg,
            "reference_marker_width_mm": self._config.reference_marker_width_mm,
            "reference_marker_height_mm": self._config.reference_marker_height_mm,
            "point_of_interest_normalized": (
                self._config.reference_point_of_interest_normalized
            ),
        }

    def _update_capture_pose(self) -> None:
        if self._robot_pose_provider is None:
            return
        try:
            pose = self._robot_pose_provider()
            if pose is None or len(pose) < 6:
                raise RuntimeError("Robot returned no valid TCP pose")
            self._pose_compensated_transformer.set_capture_pose(pose)
        except Exception:
            self._pose_compensated_transformer.clear_capture_pose()
            now = time.monotonic()
            if now - self._last_pose_error_log_s >= 5.0:
                self._last_pose_error_log_s = now
                self._logger.exception("Could not read current robot TCP pose")

    def _load_work_area_detection_region(
        self, image_width: int, image_height: int
    ) -> tuple[float, float, float, float] | None:
        try:
            if self._work_area_region_provider is not None:
                points = self._work_area_region_provider(self._config.active_work_area)
            else:
                ok, _message, pixel_points = self._vision.get_work_area(
                    self._config.active_work_area
                )
                if not ok or pixel_points is None:
                    points = None
                else:
                    points = [
                        (float(x) / image_width, float(y) / image_height)
                        for x, y in pixel_points
                    ]
            normalized_points = tuple(
                (float(point[0]), float(point[1])) for point in (points or ())
            )
            if len(normalized_points) < 3:
                self._base_region.clear()
                return None
            left = min(point[0] for point in normalized_points)
            top = min(point[1] for point in normalized_points)
            right = max(point[0] for point in normalized_points)
            bottom = max(point[1] for point in normalized_points)
            self._base_region.set(left, top, right, bottom)
            return self._base_region.normalized
        except Exception:
            self._base_region.clear()
            self._logger.exception("Could not load shaft alignment work-area region")
            return None

    def _persist_runtime_state(self, **changes) -> None:
        settings = replace(self._stored_settings, **changes)
        settings.validate()
        self._write_settings_file(settings)
        self._stored_settings = settings
        self._config = replace(self._config, **changes)

    def _write_settings_file(self, settings: ShaftAlignmentSettings) -> None:
        payload = json.dumps(settings.to_dict(), indent=2) + "\n"
        temporary = self._settings_path.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self._settings_path)

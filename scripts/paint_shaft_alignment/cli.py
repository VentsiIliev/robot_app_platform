from __future__ import annotations

import logging
import time

import cv2
import numpy as np

from .detector import ShaftMarkerDetector
from .config import CONFIG, StandaloneShaftDetectionConfig
from .coordinate_mapper import (
    MarkerCenterRobotMapper,
    MarkerPlanarSize,
    MarkerRobotPosition,
    TcpCoordinateTransformer,
)
from .models import MarkerDetection, MarkerDetectionStatus, ShaftMarkerConfig
from .paint_vision_factory import build_paint_tcp_transformer, build_paint_vision_service
from .orientation_factory import build_orientation_strategy
from .region import (
    CenteredDetectionRegionProvider,
    PixelRegion,
    SelectableDetectionRegionProvider,
)
from .stabilizer import MarkerSampleStabilizer, StableMarkerEstimate
from .tracker import MarkerRegionTracker


class _DetectionRegionMouseHandler:
    """Translates OpenCV mouse gestures into base-region selections."""

    def __init__(self, provider: SelectableDetectionRegionProvider, on_changed) -> None:
        self._provider = provider
        self._on_changed = on_changed
        self._start: tuple[int, int] | None = None
        self.preview_region: PixelRegion | None = None
        self.selection_completed = False

    def __call__(self, event, x, y, _flags, _parameter) -> None:
        point = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            self._start = point
            self.preview_region = None
        elif event == cv2.EVENT_MOUSEMOVE and self._start is not None:
            self.preview_region = self._region_between(self._start, point)
        elif event == cv2.EVENT_LBUTTONUP and self._start is not None:
            start = self._start
            self._start = None
            self.preview_region = None
            if self._provider.select(start, point):
                self.selection_completed = True
                self._on_changed()

    @staticmethod
    def _region_between(start: tuple[int, int], end: tuple[int, int]) -> PixelRegion | None:
        left, right = sorted((start[0], end[0]))
        top, bottom = sorted((start[1], end[1]))
        if left == right or top == bottom:
            return None
        return PixelRegion(left, top, right - left, bottom - top)


def _draw_detection(
    frame,
    result: MarkerDetection,
    *,
    draw_all_markers: bool,
    draw_detection_region: bool,
    debug_region: PixelRegion | None,
    tracker_state: str,
    robot_position: MarkerRobotPosition,
    draw_robot_coordinates: bool,
    stable_estimate: StableMarkerEstimate,
    planar_size: MarkerPlanarSize,
    selection_preview: PixelRegion | None = None,
):
    display = frame.copy()
    color = (40, 200, 40) if result.detected else (30, 80, 230)
    if draw_detection_region and debug_region is not None:
        region = debug_region
        cv2.rectangle(
            display,
            (region.x, region.y),
            (region.right - 1, region.bottom - 1),
            (255, 160, 0),
            2,
        )
    if selection_preview is not None:
        cv2.rectangle(
            display,
            (selection_preview.x, selection_preview.y),
            (selection_preview.right - 1, selection_preview.bottom - 1),
            (255, 255, 0),
            2,
        )
    if draw_all_markers:
        for marker in result.detected_markers:
            marker_color = (
                (40, 200, 40)
                if marker.marker_id == result.marker_id
                else (0, 210, 255)
            )
            points = [(round(x), round(y)) for x, y in marker.corners_px]
            for start, end in zip(points, points[1:] + points[:1]):
                cv2.line(display, start, end, marker_color, 2, cv2.LINE_AA)
            label_at = (round(marker.center_px[0]) + 8, round(marker.center_px[1]) - 8)
            cv2.putText(
                display,
                _marker_orientation_label(marker),
                label_at,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                marker_color,
                2,
                cv2.LINE_AA,
            )
    if result.corners_px:
        points = [(round(x), round(y)) for x, y in result.corners_px]
        for start, end in zip(points, points[1:] + points[:1]):
            cv2.line(display, start, end, color, 2, cv2.LINE_AA)
    if result.center_px is not None:
        center = (round(result.center_px[0]), round(result.center_px[1]))
        cv2.drawMarker(display, center, color, cv2.MARKER_CROSS, 24, 2)

    area_text = "n/a" if result.area_px2 is None else f"{result.area_px2:.1f}px2"
    orientation_text = (
        "n/a" if result.orientation_deg is None else f"{result.orientation_deg:+.1f}deg"
    )
    lines = [
        f"shaft marker: {result.marker_id}",
        f"status: {result.status.value}",
        f"center: {result.center_px}",
        f"area: {area_text}",
        f"orientation: {orientation_text}",
        f"tracker: {tracker_state}",
        (
            f"stable: YES samples={stable_estimate.sample_count}/{stable_estimate.required_samples}"
            if stable_estimate.stable
            else f"stable: NO samples={stable_estimate.sample_count}/{stable_estimate.required_samples}"
        ),
    ]
    if stable_estimate.center_px is not None:
        lines.append(
            f"stable center: ({stable_estimate.center_px[0]:.2f}, "
            f"{stable_estimate.center_px[1]:.2f}) spread={stable_estimate.center_spread_px:.2f}px"
        )
        lines.append(
            f"stable angle: {stable_estimate.orientation_deg:+.2f}deg "
            f"spread={stable_estimate.orientation_spread_deg:.2f}deg"
        )
    if planar_size.available:
        lines.extend(
            [
                f"marker real: {planar_size.real_size_mm:.2f} x {planar_size.real_size_mm:.2f} mm",
                f"marker measured: {planar_size.width_mm:.2f} x {planar_size.height_mm:.2f} mm",
                f"marker diff: {planar_size.width_difference_mm:+.2f} x {planar_size.height_difference_mm:+.2f} mm",
            ]
        )
    target_marker = next(
        (marker for marker in result.detected_markers if marker.marker_id == result.marker_id),
        None,
    )
    diagnostics = dict(target_marker.orientation_diagnostics) if target_marker is not None else {}
    if diagnostics:
        lines.extend(
            [
                (
                    f"PnP RX/RY: {diagnostics['solve_pnp.rx_deg']:+.2f} / "
                    f"{diagnostics['solve_pnp.ry_deg']:+.2f} deg"
                ),
                (
                    f"PnP tilt/Z: {diagnostics['solve_pnp.tilt_deg']:.2f} deg / "
                    f"{diagnostics['solve_pnp.z_mm']:.2f} mm"
                ),
                (
                    f"PnP reproj: {diagnostics['solve_pnp.reprojection_error_px']:.3f}px "
                    f"candidate {int(diagnostics['solve_pnp.selected_candidate']) + 1}/"
                    f"{int(diagnostics['solve_pnp.candidate_count'])}"
                ),
            ]
        )
    if draw_robot_coordinates:
        robot_text = (
            f"robot TCP XY: ({robot_position.x_mm:+.3f}, {robot_position.y_mm:+.3f}) mm"
            if robot_position.available
            else f"robot TCP XY: unavailable ({robot_position.message})"
        )
        lines.append(robot_text)
    for index, line in enumerate(lines):
        cv2.putText(
            display,
            line,
            (12, 28 + index * 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )
    return display


def _marker_orientation_label(marker) -> str:
    values = dict(marker.orientation_samples)
    if "corner_edge" in values and "solve_pnp" in values:
        delta = (values["solve_pnp"] - values["corner_edge"] + 180.0) % 360.0 - 180.0
        return (
            f"ID {marker.marker_id} edge={values['corner_edge']:+.1f} "
            f"pnp={values['solve_pnp']:+.1f} d={delta:+.1f} deg"
        )
    return f"ID {marker.marker_id} {marker.orientation_deg:+.1f} deg"


def _draw_region_prompt(frame, preview: PixelRegion | None):
    display = frame.copy()
    if preview is not None:
        cv2.rectangle(
            display,
            (preview.x, preview.y),
            (preview.right - 1, preview.bottom - 1),
            (255, 255, 0),
            2,
        )
    cv2.putText(
        display,
        "Drag to select initial detection region (Enter = centered default)",
        (12, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 0),
        2,
        cv2.LINE_AA,
    )
    return display


def main(config: StandaloneShaftDetectionConfig = CONFIG) -> int:
    logging.basicConfig(
        level=logging.DEBUG if config.verbose_logging else logging.INFO
    )
    runtime_config = config
    marker_config = ShaftMarkerConfig(
        marker_id=config.marker_id,
        minimum_area_px2=config.minimum_area_px2,
    )
    vision = build_paint_vision_service(runtime_config.active_work_area)
    coordinate_mapper = MarkerCenterRobotMapper(
        TcpCoordinateTransformer(build_paint_tcp_transformer(vision))
    )
    work_area_region_provider = SelectableDetectionRegionProvider(
        CenteredDetectionRegionProvider(
            width=runtime_config.base_region_width_px,
            height=runtime_config.base_region_height_px,
        )
    )
    tracker = MarkerRegionTracker(
        work_area_region_provider,
        padding_px=runtime_config.tracking_region_padding_px,
        minimum_width_px=runtime_config.tracking_region_minimum_width_px,
        minimum_height_px=runtime_config.tracking_region_minimum_height_px,
        recovery_expansion_px=runtime_config.tracking_recovery_expansion_px,
        misses_before_fallback=runtime_config.marker_misses_before_region_fallback,
        detections_before_tracking=runtime_config.detections_before_tracking,
        acquisition_misses_before_reset=runtime_config.acquisition_misses_before_reset,
        position_filter_alpha=runtime_config.tracking_position_filter_alpha,
        prediction_gain=runtime_config.tracking_prediction_gain,
        maximum_center_jump_px=runtime_config.tracking_maximum_center_jump_px,
        maximum_area_ratio_change=runtime_config.tracking_maximum_area_ratio_change,
    )
    stabilizer = MarkerSampleStabilizer(
        required_samples=runtime_config.stability_required_samples,
        maximum_center_spread_px=runtime_config.stability_maximum_center_spread_px,
        maximum_orientation_spread_deg=runtime_config.stability_maximum_orientation_spread_deg,
        misses_before_reset=runtime_config.stability_misses_before_reset,
    )
    detector = ShaftMarkerDetector(
        vision,
        marker_config,
        orientation_strategy=build_orientation_strategy(vision, runtime_config),
    )
    vision.set_raw_mode(runtime_config.raw_mode)
    vision.update_settings({"Aruco": {"Enable detection": True}})
    vision.start()
    started_at = time.monotonic()
    previous_status: MarkerDetectionStatus | None = None

    def reset_region_consumers() -> None:
        tracker.reset()
        stabilizer.reset()

    mouse_handler = _DetectionRegionMouseHandler(
        work_area_region_provider,
        reset_region_consumers,
    )

    if not runtime_config.headless:
        cv2.namedWindow(runtime_config.window_title)
        cv2.setMouseCallback(runtime_config.window_title, mouse_handler)

    print(
        "[shaft-marker] started "
        f"marker_id={marker_config.marker_id} area={runtime_config.active_work_area!r} "
        f"raw={runtime_config.raw_mode}"
    )
    if not runtime_config.headless:
        print("[shaft-marker] drag with the left mouse button to select the ROI; press r to reset it")
    awaiting_initial_region = (
        runtime_config.draw_initial_detection_region and not runtime_config.headless
    )
    try:
        while (
            runtime_config.run_duration_s <= 0.0
            or time.monotonic() - started_at < runtime_config.run_duration_s
        ):
            frame = (
                vision.get_latest_raw_frame()
                if runtime_config.raw_mode
                else vision.get_latest_frame()
            )
            detection_region = None
            frame_width = frame_height = 0
            if isinstance(frame, np.ndarray) and frame.size > 0:
                frame_height, frame_width = frame.shape[:2]
                detection_region = tracker.region_for_frame(frame_width, frame_height)
            if awaiting_initial_region and isinstance(frame, np.ndarray) and frame.size > 0:
                cv2.imshow(
                    runtime_config.window_title,
                    _draw_region_prompt(frame, mouse_handler.preview_region),
                )
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
                if mouse_handler.selection_completed or key in (10, 13):
                    awaiting_initial_region = False
                    reset_region_consumers()
                    selected = work_area_region_provider.resolve(frame_width, frame_height)
                    print(f"[shaft-marker] initial detection region={selected}")
                time.sleep(max(0.0, runtime_config.detection_interval_s))
                continue
            result = detector.detect(frame, detection_region=detection_region)
            stable_estimate = stabilizer.estimate()
            planar_size = MarkerPlanarSize(False, runtime_config.marker_size_mm)
            if result.detected:
                target = next(
                    marker
                    for marker in result.detected_markers
                    if marker.marker_id == marker_config.marker_id
                )
                if not tracker.record_detection(target):
                    tracker.record_miss()
                stable_estimate = stabilizer.record_detection(target)
                planar_size = coordinate_mapper.measure_planar_size(
                    target.corners_px,
                    runtime_config.marker_size_mm,
                )
            elif result.status is MarkerDetectionStatus.MARKER_NOT_FOUND:
                tracker.record_miss()
                stable_estimate = stabilizer.record_miss()

            robot_position = (
                coordinate_mapper.map_center(stable_estimate.center_px)
                if stable_estimate.stable and stable_estimate.center_px is not None
                else MarkerRobotPosition(False, message=stable_estimate.message)
            )

            next_region = (
                tracker.region_for_frame(frame_width, frame_height)
                if frame_width > 0 and frame_height > 0
                else None
            )
            if result.status is not previous_status or result.detected:
                print(
                    f"[shaft-marker] status={result.status.value} "
                    f"center={result.center_px} area_px2={result.area_px2} "
                    f"orientation_deg={result.orientation_deg} "
                    f"orientation_samples={target.orientation_samples if result.detected else ()} "
                    f"orientation_diagnostics={target.orientation_diagnostics if result.detected else ()} "
                    f"robot_tcp_xy_mm=({robot_position.x_mm}, {robot_position.y_mm}) "
                    f"visible_ids={result.detected_ids}"
                )
                previous_status = result.status

            if not runtime_config.headless and frame is not None:
                cv2.imshow(
                    runtime_config.window_title,
                    _draw_detection(
                        frame,
                        result,
                        draw_all_markers=runtime_config.debug_draw_detected_markers,
                        draw_detection_region=runtime_config.debug_draw_detection_region,
                        debug_region=next_region,
                        tracker_state=tracker.state.value,
                        robot_position=robot_position,
                        draw_robot_coordinates=runtime_config.debug_draw_robot_coordinates,
                        stable_estimate=stable_estimate,
                        planar_size=planar_size,
                        selection_preview=mouse_handler.preview_region,
                    ),
                )
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
                if key == ord("r"):
                    work_area_region_provider.clear()
                    reset_region_consumers()
                    print("[shaft-marker] detection region reset to configured centered ROI")
            time.sleep(max(0.0, runtime_config.detection_interval_s))
    except KeyboardInterrupt:
        pass
    finally:
        vision.stop()
        if not runtime_config.headless:
            cv2.destroyAllWindows()
        print("[shaft-marker] stopped")
    return 0

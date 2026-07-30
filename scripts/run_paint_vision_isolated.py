#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import sys
import time


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.repositories.settings_service_factory import build_from_specs
from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem
from src.engine.vision.implementation.VisionSystem.core.service.internal_service import Service
from src.engine.vision.vision_service import VisionService
from src.engine.work_areas.work_area_service import WorkAreaService
from src.robot_systems.paint.paint_robot_system import PaintRobotSystem


def _build_vision_service(active_area: str | None) -> VisionService:
    settings_service = build_from_specs(
        PaintRobotSystem.settings_specs,
        PaintRobotSystem.metadata.settings_root,
        PaintRobotSystem,
    )
    work_area_service = WorkAreaService(
        settings_service=settings_service,
        definitions=PaintRobotSystem.work_areas,
        default_active_area_id=PaintRobotSystem.default_active_work_area_id,
    )
    if active_area is not None:
        work_area_service.set_active_area_id(active_area)

    settings_repo = settings_service.get_repo(CommonSettingsID.VISION_CAMERA_SETTINGS)
    data_storage_path = PaintRobotSystem.storage_path("settings", "vision", "data")
    os.makedirs(data_storage_path, exist_ok=True)

    internal_service = Service(
        data_storage_path=data_storage_path,
        settings_file_path=settings_repo.file_path,
    )
    vision_system = VisionSystem(
        storage_path=data_storage_path,
        messaging_service=None,
        service=internal_service,
        work_area_service=work_area_service,
    )
    return VisionService(vision_system, work_area_service=work_area_service)


def _format_frame_shape(frame) -> str:
    if frame is None or not hasattr(frame, "shape"):
        return "none"
    return "x".join(str(int(v)) for v in frame.shape)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the paint vision system headless for isolated profiling."
    )
    parser.add_argument(
        "--area",
        default=PaintRobotSystem.default_active_work_area_id,
        help="Active work area id to load before starting vision.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="How long to run in seconds. Use 0 to run until Ctrl-C.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Enable raw mode instead of corrected-frame publishing behavior.",
    )
    parser.add_argument(
        "--snapshot-interval",
        type=float,
        default=0.0,
        help=(
            "If > 0, periodically call compute_contours_for_latest_frame() to simulate "
            "paint snapshot usage while profiling."
        ),
    )
    parser.add_argument(
        "--status-interval",
        type=float,
        default=5.0,
        help="How often to print runtime status in seconds.",
    )
    args = parser.parse_args()

    vision = _build_vision_service(args.area)
    vision.set_raw_mode(args.raw)
    vision.start()

    stop_requested = False

    def _handle_stop(_signum, _frame) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    start_at = time.monotonic()
    next_status_at = start_at
    next_snapshot_at = start_at + args.snapshot_interval if args.snapshot_interval > 0 else None

    print(
        "[vision-isolated] started "
        f"area={args.area!r} raw_mode={args.raw} "
        f"snapshot_interval={args.snapshot_interval}s "
        f"status_interval={args.status_interval}s"
    )
    print("[vision-isolated] profiling target is the current process; use scripts/profile_pid.sh in another shell")

    try:
        while not stop_requested:
            now = time.monotonic()
            elapsed = now - start_at
            if args.duration > 0 and elapsed >= args.duration:
                break

            if next_snapshot_at is not None and now >= next_snapshot_at:
                frame, contours = vision.compute_contours_for_latest_frame()
                print(
                    "[vision-isolated] snapshot "
                    f"elapsed={elapsed:0.1f}s frame={_format_frame_shape(frame)} "
                    f"contours={len(contours)}"
                )
                next_snapshot_at += args.snapshot_interval

            if args.status_interval > 0 and now >= next_status_at:
                raw = vision.get_latest_raw_frame()
                corrected = vision.get_latest_corrected_frame()
                print(
                    "[vision-isolated] status "
                    f"elapsed={elapsed:0.1f}s raw={_format_frame_shape(raw)} "
                    f"corrected={_format_frame_shape(corrected)} "
                    f"cached_contours={len(vision.get_latest_contours())}"
                )
                next_status_at += args.status_interval

            time.sleep(0.1)
    finally:
        vision.stop()
        print("[vision-isolated] stopped")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

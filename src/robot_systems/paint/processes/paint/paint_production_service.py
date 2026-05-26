from __future__ import annotations

import logging
from typing import Callable, Optional

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.robot_systems.paint.processes.paint.workpiece_matching_service import pick_largest_contour

_logger = logging.getLogger(__name__)


class PaintProductionService:
    """Own the end-to-end paint production flow outside the editor UI."""
    def __init__(
        self,
        *,
        workpiece_preparation_service,
        capture_snapshot_service,
        path_preparation_service,
        path_executor,
        vacuum_pump: Optional[IVacuumPumpController] = None,
    ) -> None:
        """Store the services needed to capture, prepare, plan, and execute one paint cycle."""
        self._workpiece_preparation = workpiece_preparation_service
        self._capture_snapshot_service = capture_snapshot_service
        self._path_preparation_service = path_preparation_service
        self._path_executor = path_executor
        self._vacuum_pump = vacuum_pump

    def test_pickup(self, stop_requested: Optional[Callable[[], bool]] = None) -> tuple[bool, str]:
        """Capture scene, build execution plan, and execute test pickup using it."""
        should_stop = stop_requested or (lambda: False)

        snapshot = self._capture_snapshot_service.capture_snapshot(source="paint_process")
        if should_stop():
            return False, "Test pickup cancelled"

        contour = pick_largest_contour(snapshot.contours)
        if contour is None:
            return False, "No usable contour detected"

        raw_workpiece, description = self._workpiece_preparation.prepare_workpiece(contour, snapshot.frame)
        if should_stop():
            return False, "Test pickup cancelled"

        try:
            execution_plan = self._path_preparation_service.build_execution_plan(raw_workpiece)
        except Exception as exc:
            _logger.exception("Test pickup plan generation failed")
            return False, f"Plan generation failed: {exc}"

        self._path_executor.set_execution_plan(execution_plan)
        return self._path_executor.test_pickup()

    def pickup_to_paint_position(self, stop_requested: Optional[Callable[[], bool]] = None) -> tuple[bool, str]:
        """Capture scene, pick up the detected workpiece, and stage it at the paint start pose."""
        should_stop = stop_requested or (lambda: False)

        snapshot = self._capture_snapshot_service.capture_snapshot(source="paint_process")
        if should_stop():
            return False, "Pickup to paint position cancelled"

        contour = pick_largest_contour(snapshot.contours)
        if contour is None:
            return False, "No usable contour detected"

        raw_workpiece, description = self._workpiece_preparation.prepare_workpiece(contour, snapshot.frame)
        if should_stop():
            return False, "Pickup to paint position cancelled"

        try:
            execution_plan = self._path_preparation_service.build_execution_plan(raw_workpiece)
        except Exception as exc:
            _logger.exception("Pickup to paint position plan generation failed")
            return False, f"Plan generation failed: {exc}"

        if should_stop():
            return False, "Pickup to paint position cancelled"

        self._path_executor.set_execution_plan(execution_plan)
        ok, msg = self._path_executor.execute_pickup_to_pivot(execution_plan)
        if not ok:
            return False, f"{description}: {msg}"
        return True, f"{description}: {msg}"

    def test_pre_paint_marker_position(self) -> tuple[bool, str]:
        """Test pre-paint marker detection and move to the computed offset pose."""
        return self._path_executor.test_pre_paint_marker_position()

    def run_once(self, stop_requested: Optional[Callable[[], bool]] = None) -> tuple[bool, str]:
        """Capture the scene, prepare a workpiece, build a plan, and execute pickup plus paint."""
        should_stop = stop_requested or (lambda: False)

        snapshot = self._capture_snapshot_service.capture_snapshot(source="paint_process")
        if should_stop():
            return False, "Paint process stopped"

        contour = pick_largest_contour(snapshot.contours)
        if contour is None:
            return False, "No usable contour detected"

        raw_workpiece, description = self._workpiece_preparation.prepare_workpiece(contour, snapshot.frame)
        if should_stop():
            return False, "Paint process stopped"

        try:
            execution_plan = self._path_preparation_service.build_execution_plan(raw_workpiece)
        except Exception as exc:
            _logger.exception("Paint production plan generation failed")
            return False, f"Plan generation failed: {exc}"

        if should_stop():
            return False, "Paint process stopped"

        ok, msg = self._path_executor.execute_pickup_and_paint(execution_plan)
        if not ok:
            return False, f"{description}: {msg}"

        return True, f"{description}: {msg}"

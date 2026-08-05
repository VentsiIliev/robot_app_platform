from __future__ import annotations

import logging
from time import perf_counter
from typing import Callable, Optional

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.robot_systems.paint.processes.paint.magazine_load_result import NO_WORKPIECE_AT_MAGAZINE
from src.robot_systems.paint.processes.paint.plan import pick_largest_contour

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
        paint_process_config_service=None,
        magazine_load_service=None,
    ) -> None:
        """Store the services needed to capture, prepare, plan, and execute one paint cycle."""
        self._workpiece_preparation = workpiece_preparation_service
        self._capture_snapshot_service = capture_snapshot_service
        self._path_preparation_service = path_preparation_service
        self._path_executor = path_executor
        self._vacuum_pump = vacuum_pump
        self._paint_process_config_service = paint_process_config_service
        self._magazine_load_service = magazine_load_service

    def pause_current_phase(self) -> None:
        pause_load = getattr(self._magazine_load_service, "pause_current_load", None)
        if callable(pause_load):
            pause_load()

    def resume_current_phase(self) -> None:
        resume_load = getattr(self._magazine_load_service, "resume_current_load", None)
        if callable(resume_load):
            resume_load()

    def stop_current_phase(self) -> None:
        stop_load = getattr(self._magazine_load_service, "stop_current_load", None)
        if callable(stop_load):
            stop_load()

    def run_once(self, stop_requested: Optional[Callable[[], bool]] = None) -> tuple[bool, str]:
        """Run production once, or repeat from magazine until the magazine is empty."""
        should_stop = stop_requested or (lambda: False)
        magazine_config_result = self._get_magazine_load_config()
        if not magazine_config_result[0]:
            return False, magazine_config_result[1]
        magazine_config = magazine_config_result[2]
        if self._magazine_load_service is not None and magazine_config is not None and magazine_config.enabled:
            return self._run_magazine_loop(magazine_config, should_stop)
        return self._run_single_cycle(should_stop, magazine_config=None, cycle_index=1)

    def _run_magazine_loop(self, magazine_config, should_stop: Callable[[], bool]) -> tuple[bool, str]:
        total_start = perf_counter()
        completed_cycles = 0
        while not should_stop():
            ok, msg = self._run_single_cycle(
                should_stop,
                magazine_config=magazine_config,
                cycle_index=completed_cycles + 1,
            )
            if not ok and msg == NO_WORKPIECE_AT_MAGAZINE:
                self._log_phase_timing(
                    "magazine_loop_total",
                    total_start,
                    success=True,
                    completed_cycles=completed_cycles,
                )
                if completed_cycles == 0:
                    return True, NO_WORKPIECE_AT_MAGAZINE
                return True, f"Magazine empty after {completed_cycles} paint cycle(s)"
            if not ok:
                self._log_phase_timing(
                    "magazine_loop_total",
                    total_start,
                    success=False,
                    completed_cycles=completed_cycles,
                )
                return False, msg
            completed_cycles += 1
        self._log_phase_timing(
            "magazine_loop_total",
            total_start,
            success=False,
            stopped=True,
            completed_cycles=completed_cycles,
        )
        return False, "Paint process stopped"

    def _run_single_cycle(
        self,
        should_stop: Callable[[], bool],
        *,
        magazine_config,
        cycle_index: int,
    ) -> tuple[bool, str]:
        total_start = perf_counter()

        if magazine_config is not None:
            phase_start = perf_counter()
            ok, msg = self._magazine_load_service.load_to_calibration(magazine_config, should_stop)
            self._log_phase_timing("magazine_load", phase_start, success=ok, cycle=cycle_index)
            if not ok:
                return False, msg
            if should_stop():
                return False, "Paint process stopped"

        phase_start = perf_counter()
        snapshot = self._capture_snapshot_service.capture_snapshot(source="paint_process")
        self._log_phase_timing("paint_capture", phase_start, contour_count=len(snapshot.contours or []), cycle=cycle_index)
        if should_stop():
            return False, "Paint process stopped"

        contour = pick_largest_contour(snapshot.contours)
        if contour is None:
            return False, "No usable contour detected"

        phase_start = perf_counter()
        raw_workpiece, description = self._workpiece_preparation.prepare_workpiece(contour, snapshot.frame)
        self._log_phase_timing("workpiece_preparation", phase_start, cycle=cycle_index)
        if should_stop():
            return False, "Paint process stopped"

        phase_start = perf_counter()
        try:
            execution_plan = self._path_preparation_service.build_execution_plan(
                raw_workpiece,
                skip_debug_plot=not self._path_debug_plots_enabled(),
            )
        except Exception as exc:
            _logger.exception("Paint production plan generation failed")
            return False, f"Plan generation failed: {exc}"
        self._log_phase_timing("path_preparation", phase_start, cycle=cycle_index)

        if should_stop():
            return False, "Paint process stopped"

        phase_start = perf_counter()
        execute_process = getattr(self._path_executor, "execute_paint_process", None)
        if execute_process is None:
            execute_process = self._path_executor.execute_pickup_and_paint
        ok, msg = execute_process(execution_plan)
        self._log_phase_timing("paint_execution", phase_start, success=ok, cycle=cycle_index)
        if not ok:
            return False, f"{description}: {msg}"

        self._log_phase_timing("run_once_total", total_start, success=True, cycle=cycle_index)
        return True, f"{description}: {msg}"

    def _get_magazine_load_config(self) -> tuple[bool, str, object | None]:
        config_service = self._paint_process_config_service
        if config_service is None:
            return True, "", None
        try:
            config = config_service.get_snapshot().magazine_load
        except Exception:
            _logger.exception("Failed to read magazine load settings")
            return False, "Failed to read magazine load settings", None
        return True, "", config

    def _path_debug_plots_enabled(self) -> bool:
        config_service = self._paint_process_config_service
        if config_service is None:
            return False
        try:
            return bool(getattr(config_service.get_snapshot(), "enable_path_debug_plots", False))
        except Exception:
            _logger.debug("Failed to read path debug plot setting", exc_info=True)
            return False

    @staticmethod
    def _log_phase_timing(label: str, started_at: float, **fields: object) -> None:
        suffix = " ".join(f"{key}={value}" for key, value in fields.items())
        if suffix:
            suffix = f" {suffix}"
        _logger.info("[PRODUCTION_TIMING] phase=%s elapsed_s=%.3f%s", label, perf_counter() - started_at, suffix)

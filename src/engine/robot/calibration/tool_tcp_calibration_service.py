from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol, Sequence

from src.engine.robot.calibration.tool_tcp_calibration_data import (
    ToolTcpCalibrationResult,
    ToolTcpSample,
)
from src.engine.robot.calibration.tool_tcp_pivot_solver import solve_tool_tcp_pivot


_logger = logging.getLogger(__name__)


class _RobotService(Protocol):
    def get_current_position(self) -> list: ...

    def stop_motion(self) -> bool: ...


class _ToolRegistryClient(Protocol):
    def update_tool(
        self,
        tool_id: int,
        name: str | None,
        transform: Sequence[float],
        *,
        persist: bool,
    ) -> tuple[bool, str]: ...


class ToolTcpCalibrationService:
    """Manual pivot calibration workflow for flange-to-physical-TCP offset."""

    def __init__(
        self,
        *,
        robot_service: _RobotService | None = None,
        tool_registry_client: _ToolRegistryClient | None = None,
        flange_pose_provider: Callable[[], Sequence[float] | None] | None = None,
        min_samples: int = 6,
        persist_on_save: bool = True,
    ):
        self._robot = robot_service
        self._tool_registry = tool_registry_client
        self._flange_pose_provider = flange_pose_provider
        self._min_samples = int(min_samples)
        self._persist_on_save = bool(persist_on_save)
        self._samples: list[ToolTcpSample] = []
        self._latest_result: ToolTcpCalibrationResult | None = None
        self._active_tool_id: int | None = None
        self._stopped = False

    @property
    def active_tool_id(self) -> int | None:
        return self._active_tool_id

    @property
    def latest_result(self) -> ToolTcpCalibrationResult | None:
        return self._latest_result

    def get_samples(self) -> list[ToolTcpSample]:
        return list(self._samples)

    def start(self, tool_id: int) -> None:
        resolved_tool_id = int(tool_id)
        if resolved_tool_id < 0:
            raise ValueError("tool_id must be non-negative")
        self._active_tool_id = resolved_tool_id
        self.clear_samples()
        self._stopped = False

    def capture_sample(self) -> ToolTcpSample:
        if self._stopped:
            raise RuntimeError("tool TCP calibration is stopped")
        if self._active_tool_id is None:
            raise RuntimeError("tool TCP calibration has not been started")

        pose = self._read_flange_pose()
        if pose is None:
            raise RuntimeError("failed to read current flange pose")

        sample = ToolTcpSample.from_pose(pose)
        self._samples.append(sample)
        self._latest_result = None
        _logger.info("Captured tool TCP sample #%d for tool_id=%s", len(self._samples), self._active_tool_id)
        return sample

    def clear_samples(self) -> None:
        self._samples.clear()
        self._latest_result = None

    def solve(self) -> ToolTcpCalibrationResult:
        result = solve_tool_tcp_pivot(self._samples, min_samples=self._min_samples)
        self._latest_result = result
        return result

    def save(self, result: ToolTcpCalibrationResult | None = None) -> tuple[bool, str]:
        if self._active_tool_id is None:
            return False, "Tool TCP calibration has not been started"
        if self._tool_registry is None:
            return False, "Tool registry client is not configured"

        resolved = result or self._latest_result
        if resolved is None:
            return False, "No solved Tool TCP calibration result is available"

        tool_name = f"TOOL_{self._active_tool_id}"
        try:
            ok, message = self._tool_registry.update_tool(
                self._active_tool_id,
                tool_name,
                resolved.tool_offset,
                persist=self._persist_on_save,
            )
        except Exception as exc:
            _logger.exception("Failed to save tool TCP calibration result")
            return False, f"Failed to save Tool TCP calibration: {exc}"

        if ok:
            return True, (
                "Tool TCP calibration saved: "
                f"tool_id={self._active_tool_id} offset="
                f"({resolved.tool_offset[0]:.3f}, {resolved.tool_offset[1]:.3f}, {resolved.tool_offset[2]:.3f}) mm"
            )
        return False, message or "Failed to save Tool TCP calibration"

    def stop(self) -> None:
        self._stopped = True
        if self._robot is None:
            return
        try:
            self._robot.stop_motion()
        except Exception:
            _logger.exception("Failed to stop robot motion during tool TCP calibration stop")

    def _read_flange_pose(self) -> Sequence[float] | None:
        if self._flange_pose_provider is not None:
            return self._flange_pose_provider()

        if self._robot is None:
            return None

        flange_reader = getattr(self._robot, "get_current_flange_position", None)
        if callable(flange_reader):
            return flange_reader()

        return self._robot.get_current_position()

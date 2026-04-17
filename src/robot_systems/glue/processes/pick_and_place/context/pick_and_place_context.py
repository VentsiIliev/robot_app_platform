from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.robot_systems.glue.processes.pick_and_place.errors import PickAndPlaceErrorInfo, PickAndPlaceStage


@dataclass
class PickAndPlaceContext:
    stage: PickAndPlaceStage = PickAndPlaceStage.STARTUP
    match_attempt: int = 0
    processed_count: int = 0
    current_workpiece_id: Optional[str] = None
    current_workpiece_name: Optional[str] = None
    current_gripper_id: Optional[int] = None
    current_orientation: Optional[float] = None
    current_pickup_point_px: Optional[tuple[float, float]] = None
    current_pickup_point_robot_mapped: Optional[tuple[float, float]] = None
    current_pickup_point_robot: Optional[tuple[float, float]] = None
    current_pickup_reference_delta: Optional[tuple[float, float]] = None
    current_pickup_rz: Optional[float] = None
    current_capture_pose: Optional[tuple[float, float, float, float, float, float]] = None
    active_height_source: str = "zero"
    current_height_mm: Optional[float] = None
    last_message: str = ""
    last_error: Optional[PickAndPlaceErrorInfo] = None
    holding_gripper_id: Optional[int] = None
    vacuum_active: bool = False
    simulation: bool = False
    plane: dict[str, Any] = field(default_factory=dict)

    def update_plane(self, plane_state) -> None:
        self.plane = {
            "x_offset": getattr(plane_state, "xOffset", 0.0),
            "y_offset": getattr(plane_state, "yOffset", 0.0),
            "tallest_contour": getattr(plane_state, "tallestContour", 0.0),
            "row_count": getattr(plane_state, "rowCount", 0),
            "is_full": getattr(plane_state, "isFull", False),
        }

    def set_stage(self, stage: PickAndPlaceStage, message: str = "") -> None:
        self.stage = stage
        if message:
            self.last_message = message

    def set_current_workpiece(
        self,
        workpiece_id: Optional[str],
        workpiece_name: Optional[str],
        gripper_id: Optional[int],
        orientation: Optional[float],
        pickup_point_px: Optional[tuple[float, float]] = None,
    ) -> None:
        self.current_workpiece_id = workpiece_id
        self.current_workpiece_name = workpiece_name
        self.current_gripper_id = gripper_id
        self.current_orientation = orientation
        self.current_pickup_point_px = pickup_point_px

    def clear_current_workpiece(self) -> None:
        self.current_workpiece_id = None
        self.current_workpiece_name = None
        self.current_gripper_id = None
        self.current_orientation = None
        self.current_pickup_point_px = None
        self.current_pickup_point_robot_mapped = None
        self.current_pickup_point_robot = None
        self.current_pickup_reference_delta = None
        self.current_pickup_rz = None
        self.current_height_mm = None

    def mark_error(self, error: PickAndPlaceErrorInfo) -> None:
        self.last_error = error
        self.stage = error.stage
        self.last_message = error.message

    def snapshot(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "match_attempt": self.match_attempt,
            "processed_count": self.processed_count,
            "current_workpiece_id": self.current_workpiece_id,
            "current_workpiece_name": self.current_workpiece_name,
            "current_gripper_id": self.current_gripper_id,
            "current_orientation": self.current_orientation,
            "current_pickup_point_px": list(self.current_pickup_point_px) if self.current_pickup_point_px else None,
            "current_pickup_point_robot_mapped": list(self.current_pickup_point_robot_mapped) if self.current_pickup_point_robot_mapped else None,
            "current_pickup_point_robot": list(self.current_pickup_point_robot) if self.current_pickup_point_robot else None,
            "current_pickup_reference_delta": list(self.current_pickup_reference_delta) if self.current_pickup_reference_delta else None,
            "current_pickup_rz": self.current_pickup_rz,
            "current_capture_pose": list(self.current_capture_pose) if self.current_capture_pose else None,
            "active_height_source": self.active_height_source,
            "current_height_mm": self.current_height_mm,
            "last_message": self.last_message,
            "last_error": None if self.last_error is None else {
                "code": self.last_error.code.value,
                "stage": self.last_error.stage.value,
                "message": self.last_error.message,
                "detail": self.last_error.detail,
                "recoverable": self.last_error.recoverable,
            },
            "holding_gripper_id": self.holding_gripper_id,
            "vacuum_active": self.vacuum_active,
            "simulation": self.simulation,
            "plane": dict(self.plane),
        }

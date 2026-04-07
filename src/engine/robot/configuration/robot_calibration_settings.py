from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


@dataclass
class AdaptiveMovementConfig:
    min_step_mm: float = 0.1
    max_step_mm: float = 25.0
    target_error_mm: float = 0.25
    max_error_ref: float = 100.0
    k: float = 2.0
    derivative_scaling: float = 0.5
    fast_iteration_wait: float = 1.0
    initial_align_y_scale: float = 1.0
    post_align_settle_s: float = 0.3

    @classmethod
    def from_dict(cls, data: Dict) -> 'AdaptiveMovementConfig':
        return cls(
            min_step_mm=data.get("min_step_mm", 0.1),
            max_step_mm=data.get("max_step_mm", 25.0),
            target_error_mm=data.get("target_error_mm", 0.25),
            max_error_ref=data.get("max_error_ref", 100.0),
            k=data.get("k", 2.0),
            derivative_scaling=data.get("derivative_scaling", 0.5),
            fast_iteration_wait=data.get("fast_iteration_wait", 1.0),
            initial_align_y_scale=data.get("initial_align_y_scale", 1.0),
            post_align_settle_s=float(data.get("post_align_settle_s", 0.3)),
        )

    def to_dict(self) -> Dict:
        return {
            "min_step_mm": self.min_step_mm,
            "max_step_mm": self.max_step_mm,
            "target_error_mm": self.target_error_mm,
            "max_error_ref": self.max_error_ref,
            "k": self.k,
            "derivative_scaling": self.derivative_scaling,
            "fast_iteration_wait": self.fast_iteration_wait,
            "initial_align_y_scale": self.initial_align_y_scale,
            "post_align_settle_s": self.post_align_settle_s,
        }


@dataclass
class AxisMappingConfig:
    marker_id: int = 4
    move_mm: float = 100.0
    max_attempts: int = 100
    delay_after_move_s: float = 1.0

    @classmethod
    def from_dict(cls, data: Dict) -> 'AxisMappingConfig':
        return cls(
            marker_id=int(data.get("marker_id", 4)),
            move_mm=float(data.get("move_mm", 100.0)),
            max_attempts=int(data.get("max_attempts", 100)),
            delay_after_move_s=float(data.get("delay_after_move_s", 1.0)),
        )

    def to_dict(self) -> Dict:
        return {
            "marker_id": self.marker_id,
            "move_mm": self.move_mm,
            "max_attempts": self.max_attempts,
            "delay_after_move_s": self.delay_after_move_s,
        }


@dataclass
class CameraTcpOffsetCalibrationConfig:
    run_during_robot_calibration: bool = False
    max_markers_for_tcp_capture: int = 2
    marker_id: int = 4
    rotation_step_deg: float = 15.0
    iterations: int = 4
    approach_z: float = 300.0
    approach_rx: float = 180.0
    approach_ry: float = 0.0
    approach_rz: float = 0.0
    velocity: int = 20
    acceleration: int = 10
    settle_time_s: float = 0.5
    detection_attempts: int = 20
    retry_delay_s: float = 0.1
    recenter_max_iterations: int = 20
    recenter_stability_wait_s: float = 0.4
    min_samples: int = 3
    max_acceptance_std_mm: float = 10.0

    @classmethod
    def from_dict(cls, data: Dict) -> 'CameraTcpOffsetCalibrationConfig':
        return cls(
            run_during_robot_calibration=bool(data.get("run_during_robot_calibration", False)),
            max_markers_for_tcp_capture=int(data.get("max_markers_for_tcp_capture", 2)),
            marker_id=int(data.get("marker_id", 4)),
            rotation_step_deg=float(data.get("rotation_step_deg", 15.0)),
            iterations=int(data.get("iterations", 6)),
            approach_z=float(data.get("approach_z", 300.0)),
            approach_rx=float(data.get("approach_rx", 180.0)),
            approach_ry=float(data.get("approach_ry", 0.0)),
            approach_rz=float(data.get("approach_rz", 0.0)),
            velocity=int(data.get("velocity", 20)),
            acceleration=int(data.get("acceleration", 10)),
            settle_time_s=float(data.get("settle_time_s", 0.5)),
            detection_attempts=int(data.get("detection_attempts", 20)),
            retry_delay_s=float(data.get("retry_delay_s", 0.1)),
            recenter_max_iterations=int(data.get("recenter_max_iterations", 20)),
            recenter_stability_wait_s=float(data.get("recenter_stability_wait_s", 0.4)),
            min_samples=int(data.get("min_samples", 3)),
            max_acceptance_std_mm=float(data.get("max_acceptance_std_mm", 10.0)),
        )

    def to_dict(self) -> Dict:
        return {
            "run_during_robot_calibration": self.run_during_robot_calibration,
            "max_markers_for_tcp_capture": self.max_markers_for_tcp_capture,
            "marker_id": self.marker_id,
            "rotation_step_deg": self.rotation_step_deg,
            "iterations": self.iterations,
            "approach_z": self.approach_z,
            "approach_rx": self.approach_rx,
            "approach_ry": self.approach_ry,
            "approach_rz": self.approach_rz,
            "velocity": self.velocity,
            "acceleration": self.acceleration,
            "settle_time_s": self.settle_time_s,
            "detection_attempts": self.detection_attempts,
            "retry_delay_s": self.retry_delay_s,
            "recenter_max_iterations": self.recenter_max_iterations,
            "recenter_stability_wait_s": self.recenter_stability_wait_s,
            "min_samples": self.min_samples,
            "max_acceptance_std_mm": self.max_acceptance_std_mm,
        }


@dataclass
class RobotCalibrationSettings:
    adaptive_movement: AdaptiveMovementConfig = field(default_factory=AdaptiveMovementConfig)
    axis_mapping: AxisMappingConfig = field(default_factory=AxisMappingConfig)
    camera_tcp_offset: CameraTcpOffsetCalibrationConfig = field(default_factory=CameraTcpOffsetCalibrationConfig)
    run_height_measurement: bool = True
    z_target: int = 300
    required_ids: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6, 8])
    candidate_ids: List[int] = field(default_factory=list)
    min_target_separation_px: float = 120.0
    homography_target_count: int = 16
    residual_target_count: int = 14
    validation_target_count: int = 6
    test_target_count: int = 10
    auto_skip_known_unreachable_markers: bool = True
    unreachable_marker_failure_threshold: int = 1
    known_unreachable_marker_ids: List[int] = field(default_factory=list)
    unreachable_marker_failure_counts: Dict[int, int] = field(default_factory=dict)
    velocity: int = 30
    acceleration: int = 10

    @classmethod
    def from_dict(cls, data: Dict) -> 'RobotCalibrationSettings':
        return cls(
            adaptive_movement=AdaptiveMovementConfig.from_dict(data.get("adaptive_movement_config", {})),
            axis_mapping=AxisMappingConfig.from_dict(data.get("axis_mapping_config", {})),
            camera_tcp_offset=CameraTcpOffsetCalibrationConfig.from_dict(
                data.get("camera_tcp_offset_config", {})
            ),
            run_height_measurement=bool(data.get("run_height_measurement", True)),
            z_target=data.get("z_target", 300),
            required_ids=data.get("required_ids", [0, 1, 2, 3, 4, 5, 6, 8]),
            candidate_ids=data.get("candidate_ids", []),
            min_target_separation_px=float(data.get("min_target_separation_px", 120.0)),
            homography_target_count=int(data.get("homography_target_count", 16)),
            residual_target_count=int(data.get("residual_target_count", 14)),
            validation_target_count=int(data.get("validation_target_count", 6)),
            test_target_count=int(data.get("test_target_count", 10)),
            auto_skip_known_unreachable_markers=bool(data.get("auto_skip_known_unreachable_markers", True)),
            unreachable_marker_failure_threshold=int(data.get("unreachable_marker_failure_threshold", 1)),
            known_unreachable_marker_ids=[
                int(marker_id) for marker_id in data.get("known_unreachable_marker_ids", [])
            ],
            unreachable_marker_failure_counts={
                int(marker_id): int(count)
                for marker_id, count in (data.get("unreachable_marker_failure_counts", {}) or {}).items()
            },
            velocity=int(data.get("velocity", 30)),
            acceleration=int(data.get("acceleration", 10)),
        )

    def to_dict(self) -> Dict:
        return {
            "adaptive_movement_config": self.adaptive_movement.to_dict(),
            "axis_mapping_config": self.axis_mapping.to_dict(),
            "camera_tcp_offset_config": self.camera_tcp_offset.to_dict(),
            "run_height_measurement": self.run_height_measurement,
            "z_target": self.z_target,
            "required_ids": self.required_ids,
            "candidate_ids": self.candidate_ids,
            "min_target_separation_px": self.min_target_separation_px,
            "homography_target_count": self.homography_target_count,
            "residual_target_count": self.residual_target_count,
            "validation_target_count": self.validation_target_count,
            "test_target_count": self.test_target_count,
            "auto_skip_known_unreachable_markers": self.auto_skip_known_unreachable_markers,
            "unreachable_marker_failure_threshold": self.unreachable_marker_failure_threshold,
            "known_unreachable_marker_ids": self.known_unreachable_marker_ids,
            "unreachable_marker_failure_counts": self.unreachable_marker_failure_counts,
            "velocity": self.velocity,
            "acceleration": self.acceleration,
        }


class RobotCalibrationSettingsSerializer(ISettingsSerializer[RobotCalibrationSettings]):

    @property
    def settings_type(self) -> str:
        return "robot_calibration"

    def get_default(self) -> RobotCalibrationSettings:
        return RobotCalibrationSettings()

    def to_dict(self, settings: RobotCalibrationSettings) -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> RobotCalibrationSettings:
        return RobotCalibrationSettings.from_dict(data)

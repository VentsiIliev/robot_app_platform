from typing import Callable

from src.robot_systems.paint.applications.paint_process_settings.service.i_paint_process_settings_service import (
    IPaintProcessSettingsService,
)
from src.robot_systems.paint.processes.paint.config import PaintProcessConfig
from src.robot_systems.paint.processes.paint.paint_process_config_service import (
    IPaintProcessConfigService,
)


class PaintProcessSettingsApplicationService(IPaintProcessSettingsService):
    def __init__(
        self,
        process_config_service: IPaintProcessConfigService,
        dropoff_group_provider: Callable[[], object | None] | None = None,
        current_position_provider: Callable[[], list[float] | None] | None = None,
        robot_service_provider: Callable[[], object | None] | None = None,
        robot_config_provider: Callable[[], object | None] | None = None,
        robot_tool: int = 0,
        robot_user: int = 0,
        peripherals_provider: Callable[[], object | None] | None = None,
    ):
        self._process_config_service = process_config_service
        self._dropoff_group_provider = dropoff_group_provider
        self._current_position_provider = current_position_provider
        self._robot_service_provider = robot_service_provider
        self._robot_config_provider = robot_config_provider
        self._robot_tool = int(robot_tool)
        self._robot_user = int(robot_user)
        self._peripherals_provider = peripherals_provider

    def load_settings(self) -> PaintProcessConfig:
        return self._process_config_service.get_snapshot()

    def save_settings(self, settings: PaintProcessConfig) -> None:
        self._process_config_service.save(settings)

    def is_dropoff_movement_group_configured(self) -> bool:
        return self.dropoff_movement_group_configuration_error() == ""

    def dropoff_movement_group_configuration_error(self) -> str:
        if self._dropoff_group_provider is None:
            return "Dropoff movement group lookup is not available."
        try:
            group = self._dropoff_group_provider()
        except Exception:
            return "Could not read the Dropoff movement group from Robot Settings."
        if group is None:
            return "Dropoff movement group does not exist in Robot Settings."
        try:
            velocity = float(getattr(group, "velocity", 0) or 0)
        except (TypeError, ValueError):
            return "Dropoff movement group velocity is invalid."
        if velocity <= 0:
            return "Dropoff movement group velocity must be greater than 0 in Robot Settings."
        try:
            acceleration = float(getattr(group, "acceleration", 0) or 0)
        except (TypeError, ValueError):
            return "Dropoff movement group acceleration is invalid."
        if acceleration <= 0:
            return "Dropoff movement group acceleration must be greater than 0 in Robot Settings."
        try:
            position = group.parse_position()
        except Exception:
            return "Dropoff movement group position is invalid."
        if position is None or len(position) < 6:
            return "Dropoff movement group position is missing."
        try:
            [float(position[index]) for index in range(6)]
        except (TypeError, ValueError):
            return "Dropoff movement group position is invalid."
        return ""

    def get_current_robot_position(self) -> list[float] | None:
        if self._current_position_provider is None:
            return None
        try:
            position = self._current_position_provider()
        except Exception:
            return None
        if position is None:
            return None
        try:
            values = [float(value) for value in list(position)[:6]]
        except (TypeError, ValueError):
            return None
        return values if len(values) >= 6 else None

    def get_pickup_safety_enabled(self) -> tuple[bool, bool]:
        if self._peripherals_provider is None:
            return False, False
        try:
            config = self._peripherals_provider()
            peripherals = getattr(config, "peripherals", {})
            pump = peripherals.get("vacuum_pump")
            sensor = peripherals.get("vacuum_sensor")
            return (
                bool(pump is not None and pump.enabled),
                bool(sensor is not None and sensor.enabled),
            )
        except Exception:
            return False, False

    def move_to_waypoint(self, waypoint: dict) -> bool:
        if self._robot_service_provider is None:
            return False
        try:
            robot = self._robot_service_provider()
        except Exception:
            return False
        if robot is None:
            return False
        normalized = self._normalize_waypoint(waypoint)
        if normalized is None:
            return False
        position = normalized["position"]
        vel = normalized["vel_percent"]
        acc = normalized["acc_percent"]
        tool, user = self._resolve_robot_frame()
        if normalized["motion_type"] == "linear":
            move = getattr(robot, "move_linear", None)
            if not callable(move):
                return False
            return bool(move(position, tool, user, vel, acc, normalized["blendR"], True))
        move = getattr(robot, "move_ptp", None)
        if not callable(move):
            return False
        return bool(move(position, tool, user, vel, acc, True))

    def _resolve_robot_frame(self) -> tuple[int, int]:
        if self._robot_config_provider is None:
            return self._robot_tool, self._robot_user
        try:
            config = self._robot_config_provider()
        except Exception:
            config = None
        if config is None:
            return self._robot_tool, self._robot_user
        return (
            int(getattr(config, "robot_tool", self._robot_tool)),
            int(getattr(config, "robot_user", self._robot_user)),
        )

    @staticmethod
    def _normalize_waypoint(value: object) -> dict | None:
        if isinstance(value, dict):
            raw_position = value.get("position", value.get("pose", []))
        else:
            raw_position = value
        try:
            position = [float(item) for item in list(raw_position)[:6]]
        except (TypeError, ValueError):
            return None
        if len(position) < 6:
            return None
        try:
            vel = float(value.get("vel_percent", 50.0)) if isinstance(value, dict) else 50.0
            acc = float(value.get("acc_percent", 20.0)) if isinstance(value, dict) else 20.0
            blend_r = float(value.get("blendR", value.get("blend_r", 0.0))) if isinstance(value, dict) else 0.0
        except (TypeError, ValueError):
            return None
        if not 0.0 <= vel <= 100.0 or not 0.0 <= acc <= 100.0 or blend_r < 0.0:
            return None
        motion_type = "ptp"
        if isinstance(value, dict):
            candidate = str(value.get("motion_type", value.get("type", "ptp"))).strip().lower()
            if candidate in {"ptp", "linear"}:
                motion_type = candidate
        return {
            "position": position,
            "vel_percent": vel,
            "acc_percent": acc,
            "motion_type": motion_type,
            "blendR": blend_r,
        }

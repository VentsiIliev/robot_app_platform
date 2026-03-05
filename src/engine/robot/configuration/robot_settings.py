from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


@dataclass
class SafetyLimits:
    x_min: int = -500
    x_max: int = 500
    y_min: int = -500
    y_max: int = 500
    z_min: int = 100
    z_max: int = 800
    rx_min: int = 170
    rx_max: int = 190
    ry_min: int = -10
    ry_max: int = 10
    rz_min: int = -180
    rz_max: int = 180

    @classmethod
    def from_dict(cls, data: Dict) -> 'SafetyLimits':
        return cls(
            x_min=data.get("x_min", -500),
            x_max=data.get("x_max", 500),
            y_min=data.get("y_min", -500),
            y_max=data.get("y_max", 500),
            z_min=data.get("z_min", 100),
            z_max=data.get("z_max", 800),
            rx_min=data.get("rx_min", 170),
            rx_max=data.get("rx_max", 190),
            ry_min=data.get("ry_min", -10),
            ry_max=data.get("ry_max", 10),
            rz_min=data.get("rz_min", -180),
            rz_max=data.get("rz_max", 180),
        )

    def to_dict(self) -> Dict:
        return {
            "x_min": self.x_min, "x_max": self.x_max,
            "y_min": self.y_min, "y_max": self.y_max,
            "z_min": self.z_min, "z_max": self.z_max,
            "rx_min": self.rx_min, "rx_max": self.rx_max,
            "ry_min": self.ry_min, "ry_max": self.ry_max,
            "rz_min": self.rz_min, "rz_max": self.rz_max,
        }


@dataclass
class OffsetDirectionMap:
    pos_x: bool = True
    neg_x: bool = True
    pos_y: bool = True
    neg_y: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> 'OffsetDirectionMap':
        return cls(
            pos_x=data.get("+X", True),
            neg_x=data.get("-X", True),
            pos_y=data.get("+Y", True),
            neg_y=data.get("-Y", True),
        )

    def to_dict(self) -> dict:
        return {"+X": self.pos_x, "-X": self.neg_x, "+Y": self.pos_y, "-Y": self.neg_y}


@dataclass
class MovementGroup:
    velocity: int = 0
    acceleration: int = 0
    position: Optional[str] = None
    points: List[str] = field(default_factory=list)
    iterations: int = 1
    has_iterations: bool = False
    has_trajectory_execution: bool = False

    @classmethod
    def from_dict(cls, data: Dict) -> 'MovementGroup':
        return cls(
            velocity=data.get("velocity", 0),
            acceleration=data.get("acceleration", 0),
            position=data.get("position"),
            points=data.get("points", []),
            iterations=data.get("iterations", 1),
            has_iterations=data.get("has_iterations", False),
            has_trajectory_execution=data.get("has_trajectory_execution", False),
        )

    def parse_position(self) -> Optional[List[float]]:
        if self.position is None:
            return None
        import json
        return [float(v) for v in json.loads(self.position)]

    def parse_points(self) -> List[List[float]]:
        import json
        return [[float(v) for v in json.loads(p)] for p in self.points]

    def to_dict(self) -> Dict:
        result = {
            "velocity": self.velocity,
            "acceleration": self.acceleration,
            "iterations": self.iterations,
            "has_iterations": self.has_iterations,
            "has_trajectory_execution": self.has_trajectory_execution,
        }
        if self.position:
            result["position"] = self.position
        if self.points:
            result["points"] = self.points
        return result



@dataclass
class GlobalMotionSettings:
    global_velocity: int = 100
    global_acceleration: int = 100
    emergency_decel: int = 500
    max_jog_step: int = 50

    @classmethod
    def from_dict(cls, data: Dict) -> 'GlobalMotionSettings':
        return cls(
            global_velocity=data.get("global_velocity", 100),
            global_acceleration=data.get("global_acceleration", 100),
            emergency_decel=data.get("emergency_decel", 500),
            max_jog_step=data.get("max_jog_step", 50),
        )

    def to_dict(self) -> Dict:
        return {
            "global_velocity": self.global_velocity,
            "global_acceleration": self.global_acceleration,
            "emergency_decel": self.emergency_decel,
            "max_jog_step": self.max_jog_step,
        }


@dataclass
class RobotSettings:
    robot_ip: str = "192.168.58.2"
    robot_tool: int = 0
    robot_user: int = 0
    tcp_x_offset: float = 0.0
    tcp_y_offset: float = 0.0
    tcp_x_step_distance: float = 50.0
    tcp_x_step_offset: float = 0.1
    tcp_y_step_distance: float = 50.0
    tcp_y_step_offset: float = 0.1
    offset_direction_map: OffsetDirectionMap = field(default_factory=OffsetDirectionMap)
    movement_groups: Dict[str, MovementGroup] = field(default_factory=dict)
    safety_limits: SafetyLimits = field(default_factory=SafetyLimits)
    global_motion_settings: GlobalMotionSettings = field(default_factory=GlobalMotionSettings)

    @classmethod
    def from_dict(cls, data: Dict) -> 'RobotSettings':
        movement_groups = {
            name: MovementGroup.from_dict(group_data)
            for name, group_data in data.get("MOVEMENT_GROUPS", {}).items()
        }
        return cls(
            robot_ip=data.get("ROBOT_IP", "192.168.58.2"),
            robot_tool=data.get("ROBOT_TOOL", 0),
            robot_user=data.get("ROBOT_USER", 0),
            tcp_x_offset=data.get("TCP_X_OFFSET", 0.0),
            tcp_y_offset=data.get("TCP_Y_OFFSET", 0.0),
            tcp_x_step_distance=data.get("TCP_X_STEP_DISTANCE", 50.0),
            tcp_x_step_offset=data.get("TCP_X_STEP_OFFSET", 0.1),
            tcp_y_step_distance=data.get("TCP_Y_STEP_DISTANCE", 50.0),
            tcp_y_step_offset=data.get("TCP_Y_STEP_OFFSET", 0.1),
            offset_direction_map=OffsetDirectionMap.from_dict(data.get("OFFSET_DIRECTION_MAP", {})),
            movement_groups=movement_groups,
            safety_limits=SafetyLimits.from_dict(data.get("SAFETY_LIMITS", {})),
            global_motion_settings=GlobalMotionSettings.from_dict(data.get("GLOBAL_MOTION_SETTINGS", {})),
        )

    def to_dict(self) -> Dict:
        return {
            "ROBOT_IP": self.robot_ip,
            "ROBOT_TOOL": self.robot_tool,
            "ROBOT_USER": self.robot_user,
            "TCP_X_OFFSET": self.tcp_x_offset,
            "TCP_Y_OFFSET": self.tcp_y_offset,
            "TCP_X_STEP_DISTANCE": self.tcp_x_step_distance,
            "TCP_X_STEP_OFFSET": self.tcp_x_step_offset,
            "TCP_Y_STEP_DISTANCE": self.tcp_y_step_distance,
            "TCP_Y_STEP_OFFSET": self.tcp_y_step_offset,
            "OFFSET_DIRECTION_MAP": self.offset_direction_map.to_dict(),
            "MOVEMENT_GROUPS": {name: g.to_dict() for name, g in self.movement_groups.items()},
            "SAFETY_LIMITS": self.safety_limits.to_dict(),
            "GLOBAL_MOTION_SETTINGS": self.global_motion_settings.to_dict(),
        }

    def __str__(self):
        import json
        return json.dumps(self.to_dict(), indent=4)


class RobotSettingsSerializer(ISettingsSerializer[RobotSettings]):

    @property
    def settings_type(self) -> str:
        return "robot_config"

    def get_default(self) -> RobotSettings:
        return RobotSettings()

    def to_dict(self, settings: RobotSettings) -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> RobotSettings:
        return RobotSettings.from_dict(data)

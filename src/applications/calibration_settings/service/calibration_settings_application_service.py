import math

from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.calibration_settings.service.i_calibration_settings_service import (
    ICalibrationSettingsService,
)
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.vision.camera_settings_serializer import CameraSettings
from src.engine.vision.i_vision_service import IVisionService
from src.shared_contracts.events.robot_events import RobotTopics


class CalibrationSettingsApplicationService(ICalibrationSettingsService):

    def __init__(
        self,
        settings_service: ISettingsService,
        vision_service: IVisionService | None = None,
        robot_service=None,
        messaging=None,
    ):
        self._settings_service = settings_service
        self._vision_service = vision_service
        self._robot_service = robot_service
        self._messaging = messaging
        self._workobject_points: dict[str, list[float]] = {}
        self._workobject_tool_id: int | None = None

    def load_settings(self) -> CalibrationSettingsData:
        vision = self._settings_service.get(CommonSettingsID.CALIBRATION_VISION_SETTINGS)
        robot = self._settings_service.get(CommonSettingsID.ROBOT_CALIBRATION)
        height = self._settings_service.get(CommonSettingsID.HEIGHT_MEASURING_SETTINGS)
        return CalibrationSettingsData(vision=vision, robot=robot, height=height)

    def save_settings(self, settings: CalibrationSettingsData) -> None:
        self._settings_service.save(CommonSettingsID.CALIBRATION_VISION_SETTINGS, settings.vision)
        self._settings_service.save(CommonSettingsID.ROBOT_CALIBRATION, settings.robot)
        self._settings_service.save(CommonSettingsID.HEIGHT_MEASURING_SETTINGS, settings.height)

        try:
            camera_settings = self._settings_service.get(CommonSettingsID.VISION_CAMERA_SETTINGS)
            if isinstance(camera_settings, CameraSettings):
                merged = dict(camera_settings.data)
                merged.update(settings.vision.to_dict())
                self._settings_service.save(CommonSettingsID.VISION_CAMERA_SETTINGS, CameraSettings(data=merged))
                if self._vision_service is not None:
                    self._vision_service.update_settings(merged)
        except Exception:
            pass

    def _current_robot_config(self):
        try:
            return self._settings_service.get(CommonSettingsID.ROBOT_CONFIG)
        except Exception:
            return None

    def _validate_workobject_reference_frame(self) -> tuple[bool, str]:
        robot_config = self._current_robot_config()
        user = int(getattr(robot_config, "robot_user", 0) if robot_config is not None else 0)
        if user != 0:
            return (
                False,
                "WorkObject calibration requires Robot Settings WorkObject/User ID = 0. "
                f"Current WorkObject/User ID is {user}. Change it to 0 and start again.",
            )
        return True, ""

    def capture_workobject_point(self, point_name: str) -> tuple[bool, str, dict]:
        ok, msg = self._validate_workobject_reference_frame()
        if not ok:
            return False, msg, {}
        if self._robot_service is None:
            return False, "Robot service is not configured", {}
        key = str(point_name).strip().lower()
        if key not in {"center", "x", "y"}:
            return False, f"Unknown WorkObject point '{point_name}'", {}

        robot_config = self._current_robot_config()
        tool_id = int(getattr(robot_config, "robot_tool", 0) if robot_config is not None else 0)
        if key == "center":
            self._workobject_points.clear()
            self._workobject_tool_id = tool_id
        elif "center" not in self._workobject_points:
            return False, "Capture the WorkObject center point first", {}
        elif self._workobject_tool_id != tool_id:
            return (
                False,
                f"WorkObject calibration started with Tool ID {self._workobject_tool_id}, but Robot Settings "
                f"now has Tool ID {tool_id}. Restore Tool ID {self._workobject_tool_id} or recapture center.",
                {},
            )

        set_active_tool = getattr(self._robot_service, "set_active_tool", None)
        if callable(set_active_tool) and not bool(set_active_tool(tool_id)):
            return False, f"Could not activate Robot Settings Tool ID {tool_id}", {}
        try:
            # WorkObject geometry is defined from the active TCP in robot base.
            # get_current_position() intentionally reports the active WOBJ frame.
            pose_reader = getattr(self._robot_service, "get_current_base_tcp_position", None)
            pose = pose_reader() if callable(pose_reader) else None
            if pose is None or not isinstance(pose, (list, tuple)) or len(pose) < 3:
                return False, "Robot base TCP position is unavailable", {}
        except Exception as exc:
            return False, f"Could not read robot position: {exc}", {}
        if pose is None or len(pose) < 3:
            return False, "Robot position is unavailable", {}
        self._workobject_points[key] = [float(v) for v in list(pose)[:6]]
        return True, f"Captured {key} point with Tool ID {tool_id}", {
            "point": key,
            "pose": list(self._workobject_points[key]),
            "tool_id": tool_id,
        }

    def solve_workobject(self, user_id: int, name: str = "") -> tuple[bool, str, dict]:
        frame_ok, frame_msg = self._validate_workobject_reference_frame()
        if not frame_ok:
            return False, frame_msg, {}
        robot_config = self._current_robot_config()
        current_tool_id = int(getattr(robot_config, "robot_tool", 0) if robot_config is not None else 0)
        if self._workobject_tool_id is not None and current_tool_id != self._workobject_tool_id:
            return (
                False,
                f"WorkObject points were captured with Tool ID {self._workobject_tool_id}, but Robot Settings "
                f"now has Tool ID {current_tool_id}. Restore Tool ID {self._workobject_tool_id} or recapture center.",
                {},
            )
        missing = [key for key in ("center", "x", "y") if key not in self._workobject_points]
        if missing:
            return False, f"Capture missing WorkObject point(s): {', '.join(missing)}", {}

        center = self._workobject_points["center"]
        x_point = self._workobject_points["x"]
        y_point = self._workobject_points["y"]
        x_vec = [x_point[0] - center[0], x_point[1] - center[1]]
        y_vec = [y_point[0] - center[0], y_point[1] - center[1]]
        x_len = math.hypot(x_vec[0], x_vec[1])
        y_len = math.hypot(y_vec[0], y_vec[1])
        if x_len < 1e-6:
            return False, "Center and X points are too close", {}
        if y_len < 1e-6:
            return False, "Center and Y points are too close", {}
        cross_z = x_vec[0] * y_vec[1] - x_vec[1] * y_vec[0]
        if abs(cross_z) < 1e-6:
            return False, "X and Y points are collinear", {}

        dot = x_vec[0] * y_vec[0] + x_vec[1] * y_vec[1]
        angle_deg = math.degrees(math.atan2(abs(cross_z), dot))
        if cross_z < 0.0:
            return (
                False,
                "Y point is on the -Y side of the selected X axis. "
                "Move from center in the desired +Y direction and capture Y again.",
                {},
            )
        if abs(angle_deg - 90.0) > 10.0:
            return (
                False,
                f"X and Y directions must be perpendicular; measured angle is {angle_deg:.1f} deg. "
                "Recapture X and Y approximately 90 deg apart.",
                {},
            )

        rz = math.degrees(math.atan2(x_vec[1], x_vec[0]))
        transform = [center[0], center[1], center[2], 0.0, 0.0, rz]
        payload = {
            "user_id": int(user_id),
            "calibration_tool_id": self._workobject_tool_id,
            "name": str(name).strip() or f"WOBJ_{int(user_id)}",
            "transform": transform,
            "points": {
                "center": list(center),
                "x": list(x_point),
                "y": list(y_point),
            },
            "cross_z": cross_z,
            "xy_angle_deg": angle_deg,
        }
        return True, f"WorkObject solved: rz={rz:.3f} deg", payload

    def save_workobject(self, user_id: int, name: str = "", persist: bool = True) -> tuple[bool, str, dict]:
        frame_ok, frame_msg = self._validate_workobject_reference_frame()
        if not frame_ok:
            return False, frame_msg, {}
        ok, msg, payload = self.solve_workobject(user_id, name)
        if not ok:
            return ok, msg, payload
        if self._robot_service is None:
            return False, "Robot service is not configured", payload

        updater = getattr(self._robot_service, "update_workobject_registry", None)
        if not callable(updater):
            return False, "Robot service does not support WorkObject registry updates", payload
        result = updater(
            payload["user_id"],
            name=payload["name"],
            transform=payload["transform"],
            persist=bool(persist),
        )
        if int(result) != 0:
            return False, "Failed to save WorkObject to robot runtime", payload

        robot_config = self._settings_service.get(CommonSettingsID.ROBOT_CONFIG)
        if robot_config is not None:
            robot_config.robot_user = payload["user_id"]
            self._settings_service.save(CommonSettingsID.ROBOT_CONFIG, robot_config)
            if self._messaging is not None:
                try:
                    self._messaging.publish(
                        RobotTopics.ROBOT_CONFIG_CHANGED,
                        {"robot_user": int(robot_config.robot_user)},
                    )
                except Exception:
                    pass

        setter = getattr(self._robot_service, "set_active_workobject", None)
        if callable(setter) and not bool(setter(payload["user_id"])):
            return False, "WorkObject saved, but could not activate it", payload

        return True, f"Saved WorkObject {payload['name']} as user {payload['user_id']}", payload

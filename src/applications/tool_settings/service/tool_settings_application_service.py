import logging
from typing import List, Tuple
from src.engine.repositories.interfaces.i_settings_service import ISettingsService

from src.engine.robot.configuration import ToolChangerSettings
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig
from src.engine.robot.tool_changer import ToolChangeStep
from src.engine.robot.relative_tool_calibration_service import RelativeToolCalibrationService
from src.engine.robot.tool_activation_service import ToolActivationService
from src.engine.common_settings_ids import CommonSettingsID
from .i_tool_settings_service import IToolSettingsService

_logger = logging.getLogger(__name__)


class ToolSettingsApplicationService(IToolSettingsService):

    def __init__(self, settings_service: ISettingsService, robot_service=None, tool_registry_client=None):
        self._settings = settings_service
        self._robot = robot_service
        self._registry = tool_registry_client
        self._calibration = RelativeToolCalibrationService(minimum_samples=3)

    def _load(self) -> ToolChangerSettings:
        return self._settings.get(CommonSettingsID.TOOL_CHANGER_CONFIG)

    def _save(self, tc: ToolChangerSettings) -> None:
        self._settings.save(CommonSettingsID.TOOL_CHANGER_CONFIG, tc)

    def get_tools(self) -> List[ToolDefinition]:
        return self._load().tools

    def add_tool(self, tool_id: int, name: str) -> Tuple[bool, str]:
        tc = self._load()
        if any(t.id == tool_id for t in tc.tools):
            return False, f"Tool ID {tool_id} already exists"
        tc.tools.append(ToolDefinition(tool_id, name))
        self._save(tc)
        return True, "Tool added"

    def update_tool(self, tool_id: int, name: str) -> Tuple[bool, str]:
        tc = self._load()
        for t in tc.tools:
            if t.id == tool_id:
                t.name = name
                self._save(tc)
                return True, "Tool updated"
        return False, f"Tool {tool_id} not found"

    def remove_tool(self, tool_id: int) -> Tuple[bool, str]:
        tc = self._load()
        if any(s.tool_id == tool_id for s in tc.slots):
            return False, f"Tool {tool_id} is assigned to a slot — unassign it first"
        before = len(tc.tools)
        tc.tools = [t for t in tc.tools if t.id != tool_id]
        if len(tc.tools) == before:
            return False, f"Tool {tool_id} not found"
        self._save(tc)
        return True, "Tool removed"

    def get_slots(self) -> List[SlotConfig]:
        return self._load().slots

    def update_slot(self, slot_id: int, tool_id) -> Tuple[bool, str]:
        """tool_id=None unassigns the slot."""
        tc = self._load()
        if tool_id is not None and not any(t.id == tool_id for t in tc.tools):
            return False, f"Tool ID {tool_id} does not exist"
        for s in tc.slots:
            if s.id == slot_id:
                s.tool_id = tool_id
                self._save(tc)
                return True, "Slot updated"
        return False, f"Slot {slot_id} not found"

    def add_slot(self, slot_id: int, tool_id) -> Tuple[bool, str]:
        """tool_id=None creates an unassigned slot."""
        tc = self._load()
        if any(s.id == slot_id for s in tc.slots):
            return False, f"Slot ID {slot_id} already exists"
        if tool_id is not None and not any(t.id == tool_id for t in tc.tools):
            return False, f"Tool ID {tool_id} does not exist"
        tc.slots.append(SlotConfig(id=slot_id, tool_id=tool_id))
        self._save(tc)
        return True, "Slot added"

    def remove_slot(self, slot_id: int) -> Tuple[bool, str]:
        tc = self._load()
        before = len(tc.slots)
        tc.slots = [s for s in tc.slots if s.id != slot_id]
        if len(tc.slots) == before:
            return False, f"Slot {slot_id} not found"
        self._save(tc)
        return True, "Slot removed"

    def update_tool_geometry(
        self, tool_id: int, relative_transform: list[float], collision_profile: str = ""
    ) -> Tuple[bool, str]:
        if len(relative_transform) != 6:
            return False, "Relative transform must contain X, Y, Z, RX, RY, RZ"
        tc = self._load()
        for tool in tc.tools:
            if tool.id == int(tool_id):
                tool.reference_tool_id = int(tc.reference_tool_id)
                tool.relative_transform = [float(value) for value in relative_transform]
                tool.collision_profile = str(collision_profile or "").strip()
                self._save(tc)
                return True, "Tool geometry updated"
        return False, f"Tool {tool_id} not found"

    def update_slot_sequences(
        self, slot_id: int, pickup: list[dict], dropoff: list[dict]
    ) -> Tuple[bool, str]:
        try:
            pickup_steps = [ToolChangeStep.from_dict(step) for step in pickup]
            dropoff_steps = [ToolChangeStep.from_dict(step) for step in dropoff]
        except (TypeError, ValueError) as exc:
            return False, str(exc)
        tc = self._load()
        for slot in tc.slots:
            if slot.id == int(slot_id):
                slot.pickup_sequence = pickup_steps
                slot.dropoff_sequence = dropoff_steps
                self._save(tc)
                return True, "Slot sequences updated"
        return False, f"Slot {slot_id} not found"

    def capture_reference_contact(self) -> Tuple[bool, str]:
        if self._robot is None or self._registry is None:
            return False, "Robot tool calibration is not configured"
        try:
            self._require_stationary_robot()
            reference_id = self._load().reference_tool_id
            reference = self._registry_transform(reference_id)
            flange = self._robot.get_current_flange_position()
            self._calibration.capture_reference(flange, reference)
            return True, f"Reference contact captured with tool {reference_id}"
        except Exception as exc:
            _logger.exception("Failed to capture reference tool contact")
            return False, str(exc)

    def capture_tool_contact(self) -> Tuple[bool, str, dict]:
        if self._robot is None:
            return False, "Robot tool calibration is not configured", {}
        try:
            self._require_stationary_robot()
            sample = self._calibration.capture_candidate(
                self._robot.get_current_flange_position()
            )
            return True, "Tool contact sample captured", {"candidate_tcp_xyz": sample}
        except Exception as exc:
            return False, str(exc), {}

    def solve_tool_calibration(self, tool_id: int) -> Tuple[bool, str, dict]:
        try:
            result = self._calibration.solve()
        except Exception as exc:
            return False, str(exc), {}
        ok, message = self.update_tool_geometry(
            int(tool_id), result["relative_transform"], self._tool_collision_profile(tool_id)
        )
        return ok, message, result if ok else {}

    def activate_tool(self, tool_id: int) -> Tuple[bool, str]:
        if self._robot is None or self._registry is None:
            return False, "Robot tool activation is not configured"
        tc = self._load()
        tool = next((item for item in tc.tools if item.id == int(tool_id)), None)
        if tool is None:
            return False, f"Tool {tool_id} not found"
        try:
            self._require_stationary_robot()
            reference = self._registry_transform(tc.reference_tool_id)
            ok, message, _ = ToolActivationService(self._registry, self._robot).activate(
                tool_id=tool.id,
                name=f"TOOL_{tool.id}",
                reference_transform=reference,
                relative_transform=tool.relative_transform,
                collision_profile=tool.collision_profile,
            )
            if ok:
                config = self._settings.get(CommonSettingsID.ROBOT_CONFIG)
                config.robot_tool = int(tool.id)
                self._settings.save(CommonSettingsID.ROBOT_CONFIG, config)
            return ok, message
        except Exception as exc:
            _logger.exception("Failed to activate tool %s", tool_id)
            return False, str(exc)

    def get_current_motion_pose(self) -> Tuple[bool, str, list[float]]:
        if self._robot is None:
            return False, "Robot motion teaching is not configured", []
        try:
            pose = [float(value) for value in self._robot.get_current_position()]
            if len(pose) != 6:
                return False, "Robot returned an invalid current pose", []
            return True, "Current pose captured", pose
        except Exception as exc:
            return False, str(exc), []

    def _tool_collision_profile(self, tool_id: int) -> str:
        tool = next((item for item in self._load().tools if item.id == int(tool_id)), None)
        return str(getattr(tool, "collision_profile", "") or "")

    def _require_stationary_robot(self) -> None:
        if self._robot is None:
            raise RuntimeError("Robot is unavailable")
        state = str(self._robot.get_state() or "").strip().lower()
        if state in {"moving", "running", "executing", "busy"}:
            raise RuntimeError(f"Robot must be stationary (current state: {state})")
        velocity = self._robot.get_current_velocity()
        if velocity is not None and abs(float(velocity)) > 0.01:
            raise RuntimeError("Robot must be stationary before tool setup")

    def _registry_transform(self, tool_id: int) -> list[float]:
        snapshot = self._registry.get_tool_registry()
        if not snapshot:
            raise RuntimeError("Robot tool registry is unavailable")
        id_map = snapshot.get("tool_id_map", {})
        name = id_map.get(int(tool_id), id_map.get(str(int(tool_id)), f"TOOL_{int(tool_id)}"))
        transform = snapshot.get("tool_registry", {}).get(name)
        if transform is None or len(transform) != 6:
            raise RuntimeError(f"Tool {tool_id} is missing from the robot registry")
        return [float(value) for value in transform]

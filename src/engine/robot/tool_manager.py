import logging
import time
import threading
from typing import Optional, Tuple, List

from .interfaces import IToolService
from .interfaces.i_tool_changer import IToolChanger
from .interfaces.i_motion_service import IMotionService
from .interfaces.tool_definition import ToolDefinition
from src.shared_contracts.declarations import ToolSlotDefinition


class ToolManager(IToolService):

    _TRANSIENT_ERROR = "Request-sent"

    def __init__(
        self,
        motion_service: IMotionService,
        tool_changer:   IToolChanger,
        robot_config,
        movement_groups,
        slot_definitions: List[ToolSlotDefinition] | None = None,
        tool_activator=None,
        operator_confirmation=None,
    ):
        self._motion         = motion_service
        self._tool_changer   = tool_changer
        self._robot_config   = robot_config
        self._movement_groups = movement_groups
        self._slot_definitions = {
            int(slot.id): slot for slot in (slot_definitions or [])
        }
        self._current_gripper: Optional[int] = None
        self._tool_activator = tool_activator
        self._operator_confirmation = operator_confirmation
        self._lock           = threading.Lock()
        self._logger         = logging.getLogger(self.__class__.__name__)
        self._tools: dict    = {}

    @property
    def current_gripper(self) -> Optional[int]:
        return self._current_gripper

    @property
    def current_tool(self) -> Optional[int]:
        return self._current_gripper

    def pickup_tool(self, tool_id: int, max_retries: int = 3) -> Tuple[bool, Optional[str]]:
        return self.pickup_gripper(tool_id, max_retries=max_retries)

    def drop_off_tool(self, tool_id: int, max_retries: int = 3) -> Tuple[bool, Optional[str]]:
        return self.drop_off_gripper(tool_id, max_retries=max_retries)

    def add_tool(self, name: str, tool) -> None:
        self._tools[name] = tool

    def get_tool(self, name: str):
        return self._tools.get(name)

    def verify_gripper_change(self, target_gripper_id: int) -> bool:
        with self._lock:
            return self._current_gripper == target_gripper_id

    def pickup_gripper(self, gripper_id: int, max_retries: int = 3) -> Tuple[bool, Optional[str]]:
        self._logger.debug("Attempting to pickup gripper %d", gripper_id)

        with self._lock:
            if self._current_gripper == gripper_id:
                self._logger.warning("Gripper already attached: %d", gripper_id)
                return False, f"Gripper {gripper_id} is already held"

            sequence = self._get_taught_sequence(gripper_id, "PICKUP")
            if sequence:
                ok, err = self._execute_taught_sequence(sequence, gripper_id, "pickup")
                if not ok:
                    return False, err
                positions, config = [], None
            else:
                positions, config = self._get_positions_and_config(gripper_id, "PICKUP")
            if positions is None or config is None:
                if not sequence:
                    self._logger.warning("No pickup config for gripper %d", gripper_id)
                    return False, f"No pickup movement group configured for gripper {gripper_id}"

            if not sequence:
                ok, err = self._execute_positions(positions, config, gripper_id, "pickup", max_retries)
                if not ok:
                    return False, err

            slot_id = self._tool_changer.get_slot_id_by_tool_id(gripper_id)
            if slot_id is None:
                return False, f"No slot found for gripper {gripper_id}"
            self._tool_changer.set_slot_available(slot_id)
            self._current_gripper = gripper_id      # ← was self.current_gripper (property, no setter)
            return True, None

    def drop_off_gripper(self, gripper_id: int, max_retries: int = 3) -> Tuple[bool, Optional[str]]:

        with self._lock:
            if self._current_gripper != gripper_id:
                return False, f"Gripper {gripper_id} is not currently held"

            slot_id = self._tool_changer.get_slot_id_by_tool_id(gripper_id)
            if slot_id is None:
                return False, f"No slot found for gripper {gripper_id}"
            if self._tool_changer.is_slot_occupied(slot_id):
                return False, f"Slot {slot_id} is already occupied"

            sequence = self._get_taught_sequence(gripper_id, "DROPOFF")
            if sequence:
                ok, err = self._execute_taught_sequence(sequence, gripper_id, "dropoff")
                if not ok:
                    return False, err
                positions, config = [], None
            else:
                positions, config = self._get_positions_and_config(gripper_id, "DROPOFF")
            if positions is None or config is None:
                if not sequence:
                    return False, f"No dropoff movement group configured for gripper {gripper_id}"

            if not sequence:
                ok, err = self._execute_positions(positions, config, gripper_id, "dropoff", max_retries)
                if not ok:
                    return False, err

            self._tool_changer.set_slot_not_available(slot_id)
            self._current_gripper = None            # ← was self.current_gripper (property, no setter)
            return True, None

    def get_tools(self) -> List[ToolDefinition]:
        return self._tool_changer.list_tools()

    # ── Internal ──────────────────────────────────────────────────────

    def _get_taught_sequence(self, tool_id: int, operation: str):
        slot_id = self._tool_changer.get_slot_id_by_tool_id(tool_id)
        if slot_id is None:
            return []
        slot = getattr(self._tool_changer, "get_slot", lambda _slot_id: None)(slot_id)
        if slot is None:
            return []
        return list(slot.pickup_sequence if operation == "PICKUP" else slot.dropoff_sequence)

    def _execute_taught_sequence(self, steps, tool_id: int, operation: str):
        for index, step in enumerate(steps):
            if step.kind == "motion":
                mover = self._motion.move_ptp if step.motion_type == "ptp" else self._motion.move_linear
                kwargs = dict(
                    position=step.pose,
                    tool=self._robot_config.robot_tool,
                    user=self._robot_config.robot_user,
                    velocity=step.velocity,
                    acceleration=step.acceleration,
                    wait_to_reach=True,
                )
                if step.motion_type != "ptp":
                    kwargs["blendR"] = step.blend_radius
                if not mover(**kwargs):
                    return False, f"{operation} step {index + 1} failed"
            elif step.kind == "wait":
                time.sleep(max(0.0, step.wait_seconds))
            elif step.kind == "operator_confirm":
                if not callable(self._operator_confirmation) or not self._operator_confirmation(step.label):
                    return False, f"Operator confirmation required at {operation} step {index + 1}"
            elif step.kind == "attach":
                if self._tool_activator is not None and not self._tool_activator.set_active_tool(tool_id):
                    return False, f"Failed to activate tool {tool_id}"
                self._robot_config.robot_tool = int(tool_id)
            elif step.kind == "detach":
                if self._tool_activator is not None and not self._tool_activator.set_active_tool(0):
                    return False, "Failed to activate flange tool 0"
                self._robot_config.robot_tool = 0
        return True, None

    def _get_positions_and_config(self, gripper_id: int, operation: str):
        """
        Resolves positions and motion config for a gripper operation.
        Prefers declared slot-to-movement-group bindings and falls back to the
        historical "SLOT {slot_id} {PICKUP|DROPOFF}" naming convention.
        """
        slot_id = self._tool_changer.get_slot_id_by_tool_id(gripper_id)
        if slot_id is None:
            self._logger.warning("No slot found for gripper_id=%d", gripper_id)
            return None, None

        group_name = self._resolve_group_name(slot_id, operation)
        if not group_name:
            self._logger.warning(
                "No declared %s movement group for slot_id=%d",
                operation.lower(),
                slot_id,
            )
            return None, None
        group = self._movement_groups.movement_groups.get(group_name)
        if group is None:
            self._logger.warning(
                "Movement group '%s' not found in robot config — available: %s",
                group_name, list(self._movement_groups.movement_groups.keys()),
            )
            return None, None

        positions = self._positions_from_group(group)
        if not positions:
            self._logger.warning("Movement group '%s' has no positions defined", group_name)
            return None, None

        return positions, group

    def _resolve_group_name(self, slot_id: int, operation: str) -> str:
        slot = self._slot_definitions.get(int(slot_id))
        if slot is not None:
            if operation == "PICKUP" and slot.pickup_movement_group_id:
                return slot.pickup_movement_group_id
            if operation == "DROPOFF" and slot.dropoff_movement_group_id:
                return slot.dropoff_movement_group_id
        return f"SLOT {slot_id} {operation}"

    def _positions_from_group(self, group) -> List[List[float]]:
        """Returns list of positions from a MovementGroup (points take priority over position)."""
        if group.points:
            return group.parse_points()
        pos = group.parse_position()
        return [pos] if pos is not None else []

    def _execute_positions(self, positions, config, gripper_id, op, max_retries) -> Tuple[bool, Optional[str]]:
        for pos_index, pos in enumerate(positions):
            ok, err = self._move_with_retry(pos, config, gripper_id, pos_index, len(positions), op, max_retries)
            if not ok:
                self._logger.error(f"Failed to move position {pos_index} position: {pos} err: {err}")
                return False, f"Failed at position {pos_index + 1}/{len(positions)}: {err}"
        return True, None

    def _move_with_retry(self, pos, config, gripper_id, pos_index, total, op, max_retries) -> Tuple[bool, Optional[str]]:
        last_error = None
        for attempt in range(max_retries):
            try:
                success = self._motion.move_linear(
                    position=pos,
                    tool=self._robot_config.robot_tool,
                    user=self._robot_config.robot_user,
                    velocity=config.velocity,
                    acceleration=config.acceleration,
                    blendR=1,
                    wait_to_reach=True,
                )
                if success:
                    return True, None
                last_error = "move_linear returned False"
            except Exception as e:
                last_error = str(e)
                if self._TRANSIENT_ERROR in last_error and attempt < max_retries - 1:
                    wait = 0.2 * (attempt + 1)
                    self._logger.warning(
                        "Transient error gripper=%s op=%s pos=%d/%d attempt=%d/%d — retrying in %.1fs",
                        gripper_id, op, pos_index + 1, total, attempt + 1, max_retries, wait,
                    )
                    time.sleep(wait)
                    continue
                self._logger.exception("Non-transient error during %s", op)
                break
            time.sleep(0.2 * (attempt + 1))
        return False, last_error

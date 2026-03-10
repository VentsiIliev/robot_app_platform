import logging
import time
import threading
from typing import Optional, Tuple, List

from .interfaces import IToolService
from .interfaces.i_tool_changer import IToolChanger
from .interfaces.i_motion_service import IMotionService
from .interfaces.tool_definition import ToolDefinition


class ToolManager(IToolService):

    _TRANSIENT_ERROR = "Request-sent"

    def __init__(
        self,
        motion_service: IMotionService,
        tool_changer:   IToolChanger,
        robot_config,
    ):
        self._motion         = motion_service
        self._tool_changer   = tool_changer
        self._robot_config   = robot_config
        self._current_gripper: Optional[int] = None
        self._lock           = threading.Lock()
        self._logger         = logging.getLogger(self.__class__.__name__)
        self._tools: dict    = {}

    @property
    def current_gripper(self) -> Optional[int]:
        return self._current_gripper

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

            positions, config = self._get_positions_and_config(gripper_id, "PICKUP")
            if positions is None or config is None:
                self._logger.warning("No pickup config for gripper %d", gripper_id)
                return False, f"No pickup movement group configured for gripper {gripper_id}"

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

            positions, config = self._get_positions_and_config(gripper_id, "DROPOFF")
            if positions is None or config is None:
                return False, f"No dropoff movement group configured for gripper {gripper_id}"

            ok, err = self._execute_positions(positions, config, gripper_id, "dropoff", max_retries)
            if not ok:
                return False, err

            self._tool_changer.set_slot_not_available(slot_id)
            self._current_gripper = None            # ← was self.current_gripper (property, no setter)
            return True, None

    def get_tools(self) -> List[ToolDefinition]:
        return self._tool_changer.list_tools()

    # ── Internal ──────────────────────────────────────────────────────

    def _get_positions_and_config(self, gripper_id: int, operation: str):
        """
        Resolves positions and motion config for a gripper operation.
        Uses naming convention: "SLOT {slot_id} {PICKUP|DROPOFF}" from robot config movement groups.
        """
        slot_id = self._tool_changer.get_slot_id_by_tool_id(gripper_id)
        if slot_id is None:
            self._logger.warning("No slot found for gripper_id=%d", gripper_id)
            return None, None

        group_name = f"SLOT {slot_id} {operation}"
        group = self._robot_config.movement_groups.get(group_name)
        if group is None:
            self._logger.warning(
                "Movement group '%s' not found in robot config — available: %s",
                group_name, list(self._robot_config.movement_groups.keys()),
            )
            return None, None

        positions = self._positions_from_group(group)
        if not positions:
            self._logger.warning("Movement group '%s' has no positions defined", group_name)
            return None, None

        return positions, group

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

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
        tool_changer: IToolChanger,        # ← interface, not concrete class
        robot_config,
    ):
        self._motion = motion_service
        self._tool_changer = tool_changer
        self._robot_config = robot_config
        self._current_gripper: Optional[int] = None
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._tools: dict = {}

    @property
    def current_gripper(self) -> Optional[int]:
        return self._current_gripper

    def add_tool(self, name: str, tool) -> None:
        self._tools[name] = tool

    def get_tool(self, name: str):
        return self._tools.get(name)

    def verify_gripper_change(self, target_gripper_id: int) -> bool:
        with self._lock:
            return self.current_gripper == target_gripper_id

    def pickup_gripper(self, gripper_id: int, max_retries: int = 3) -> Tuple[bool, Optional[str]]:
        with self._lock:
            if self.current_gripper == gripper_id:
                return False, f"Gripper {gripper_id} is already held"

            positions, config = self._get_pickup_positions_and_config(gripper_id)
            if positions is None or config is None:
                return False, f"Unsupported gripper ID: {gripper_id}"

            ok, err = self._execute_positions(positions, config, gripper_id, "pickup", max_retries)
            if not ok:
                return False, err

            slot_id = self._tool_changer.get_slot_id_by_tool_id(gripper_id)
            if slot_id is None:
                return False, f"No slot found for gripper {gripper_id}"
            self._tool_changer.set_slot_available(slot_id)
            self.current_gripper = gripper_id
            return True, None

    def drop_off_gripper(self, gripper_id: int, max_retries: int = 3) -> Tuple[bool, Optional[str]]:
        with self._lock:
            if self.current_gripper != gripper_id:
                return False, f"Gripper {gripper_id} is not currently held"

            slot_id = self._tool_changer.get_slot_id_by_tool_id(gripper_id)
            if slot_id is None:
                return False, f"No slot found for gripper {gripper_id}"
            if self._tool_changer.is_slot_occupied(slot_id):
                return False, f"Slot {slot_id} is already occupied"

            positions, config = self._get_dropoff_positions_and_config(gripper_id)
            if positions is None or config is None:
                return False, f"Unsupported gripper ID: {gripper_id}"

            ok, err = self._execute_positions(positions, config, gripper_id, "dropoff", max_retries)
            if not ok:
                return False, err

            self._tool_changer.set_slot_not_available(slot_id)
            self.current_gripper = None
            return True, None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _execute_positions(self, positions, config, gripper_id, op, max_retries) -> Tuple[bool, Optional[str]]:
        for pos_index, pos in enumerate(positions):
            ok, err = self._move_with_retry(pos, config, gripper_id, pos_index, len(positions), op, max_retries)
            if not ok:
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

    def _get_pickup_positions_and_config(self, gripper_id):
        cfg = self._robot_config
        table = {
            0: (cfg.getSlot0PickupPointsParsed, cfg.getSlot0PickupConfig),
            1: (cfg.getSlot1PickupPointsParsed, cfg.getSlot1PickupConfig),
            4: (cfg.getSlot4PickupPointsParsed, cfg.getSlot4PickupConfig),
        }
        if gripper_id not in table:
            return None, None
        return table[gripper_id][0](), table[gripper_id][1]()

    def _get_dropoff_positions_and_config(self, gripper_id):
        cfg = self._robot_config
        table = {
            0: (cfg.getSlot0DropoffPointsParsed, cfg.getSlot0DropoffConfig),
            1: (cfg.getSlot1DropoffPointsParsed, cfg.getSlot1DropoffConfig),
            4: (cfg.getSlot4DropoffPointsParsed, cfg.getSlot4DropoffConfig),
        }
        if gripper_id not in table:
            return None, None
        return table[gripper_id][0](), table[gripper_id][1]()

    def get_tools(self) -> List[ToolDefinition]:
        return self._tool_changer.list_tools()
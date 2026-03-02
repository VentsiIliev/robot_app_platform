import threading
import time
from typing import Optional, Tuple


from modules.shared.tools.ToolChanger import ToolChanger


class ToolManager:
    """
    Manages gripper/tool pickup and drop-off in a decoupled way.
    RobotService delegates tool operations to this manager.
    """

    def __init__(self, tool_changer: ToolChanger, robot_service):
        self.tool_changer = tool_changer
        self.robot_service = robot_service
        self.current_gripper: Optional[int] = None
        self._lock = threading.Lock()
        self.tools = {}

    @property
    def pump(self):
        return self.tools.get("vacuum_pump")

    @property
    def laser(self):
        return self.tools.get("laser")

    def add_tool(self,name,tool):
        self.tools[name] = tool

    def get_tool(self,name):
        tool = self.tools.get(name)
        return tool

    def verify_gripper_change(self,target_gripper_id:int)->bool:
        """Verify if a gripper change is possible."""
        with self._lock:
            if int(self.current_gripper) == int(target_gripper_id):
                return True
            else:
                return  False

    def pickup_gripper(self, gripper_id: int, max_retries: int = 3) -> Tuple[bool, Optional[str]]:
        """
        Pick up a gripper/tool from its slot with retry logic.

        Args:
            gripper_id: ID of the gripper to pick up
            max_retries: Maximum number of retry attempts for transient errors

        Returns:
            Tuple of (success, error_message)
        """
        with self._lock:
            if self.current_gripper == gripper_id:
                return False, f"Gripper {gripper_id} is already picked"

            positions, config = self._get_pickup_positions_and_config(gripper_id)
            if positions is None or config is None:
                return False, f"Unsupported gripper ID: {gripper_id}"

            # Retry logic for each movement position
            for pos_index, pos in enumerate(positions):
                success = False
                last_error = None

                for attempt in range(max_retries):
                    try:
                        result = self.robot_service.robot.move_cartesian(
                            position=pos,
                            tool=self.robot_service.robot_config.robot_tool,
                            user=self.robot_service.robot_config.robot_user,
                            vel=config.velocity,
                            acc=config.acceleration,
                            blendR=1
                        )

                        # Check if move succeeded (result == 0)
                        if isinstance(result, int) and result == 0:
                            success = True
                            break
                        else:
                            last_error = f"Move returned error code: {result}"
                            if attempt < max_retries - 1:
                                time.sleep(0.2 * (attempt + 1))  # Exponential backoff

                    except Exception as e:
                        error_str = str(e)
                        last_error = error_str

                        # Check if it's a "Request-sent" transient error
                        if "Request-sent" in error_str and attempt < max_retries - 1:
                            # Wait before retry with exponential backoff
                            wait_time = 0.2 * (attempt + 1)
                            print(f"Transient error during gripper {gripper_id} pickup (position {pos_index + 1}/{len(positions)}, attempt {attempt + 1}/{max_retries}): {error_str}. Retrying in {wait_time}s...")
                            time.sleep(wait_time)
                            continue
                        else:
                            # Non-transient error or max retries reached
                            import traceback
                            traceback.print_exc()
                            break

                # If all retries failed for this position, return error
                if not success:
                    return False, f"Failed at position {pos_index + 1}/{len(positions)}: {last_error}"

            # All positions completed successfully - update slot state
            try:
                slot_id = self.tool_changer.getSlotIdByGrippedId(gripper_id)
                self.tool_changer.setSlotAvailable(slot_id)
            except Exception as e:
                import traceback
                traceback.print_exc()
                return False, f"Failed to update slot state: {str(e)}"

            # Move to start position with retry
            for attempt in range(max_retries):
                try:
                    result = self.robot_service.moveToStartPosition()
                    if isinstance(result, int) and result == 0:
                        break
                    elif attempt < max_retries - 1:
                        time.sleep(0.2 * (attempt + 1))
                except Exception as e:
                    if "Request-sent" in str(e) and attempt < max_retries - 1:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    else:
                        return False, f"Failed to move to start position: {str(e)}"

            self.current_gripper = gripper_id
            return True, None

    def drop_off_gripper(self, gripper_id: int, max_retries: int = 3) -> Tuple[bool, Optional[str]]:
        """
        Drop the currently held gripper/tool into its slot with retry logic.

        Args:
            gripper_id: ID of the gripper to drop off
            max_retries: Maximum number of retry attempts for transient errors

        Returns:
            Tuple of (success, error_message)
        """
        with self._lock:
            if self.current_gripper != gripper_id:
                return False, f"Gripper {gripper_id} is not currently held"

            slot_id = self.tool_changer.getSlotIdByGrippedId(gripper_id)
            if self.tool_changer.isSlotOccupied(slot_id):
                return False, f"Slot {slot_id} is already occupied"

            positions, config = self._get_dropoff_positions_and_config(gripper_id)
            if positions is None or config is None:
                return False, f"Unsupported gripper ID: {gripper_id}"

            # Retry logic for each movement position
            for pos_index, pos in enumerate(positions):
                success = False
                last_error = None

                for attempt in range(max_retries):
                    try:
                        result = self.robot_service.robot.move_cartesian(
                            position=pos,
                            tool=self.robot_service.robot_config.robot_tool,
                            user=self.robot_service.robot_config.robot_user,
                            vel=config.velocity,
                            acc=config.acceleration,
                            blendR=1
                        )

                        # Check if move succeeded (result == 0)
                        if isinstance(result, int) and result == 0:
                            success = True
                            break
                        else:
                            last_error = f"Move returned error code: {result}"
                            if attempt < max_retries - 1:
                                time.sleep(0.2 * (attempt + 1))

                    except Exception as e:
                        error_str = str(e)
                        last_error = error_str

                        # Check if it's a "Request-sent" transient error
                        if "Request-sent" in error_str and attempt < max_retries - 1:
                            # Wait before retry with exponential backoff
                            wait_time = 0.2 * (attempt + 1)
                            print(f"Transient error during gripper {gripper_id} dropoff (position {pos_index + 1}/{len(positions)}, attempt {attempt + 1}/{max_retries}): {error_str}. Retrying in {wait_time}s...")
                            time.sleep(wait_time)
                            continue
                        else:
                            # Non-transient error or max retries reached
                            import traceback
                            traceback.print_exc()
                            break

                # If all retries failed for this position, return error
                if not success:
                    return False, f"Failed at position {pos_index + 1}/{len(positions)}: {last_error}"

            # All positions completed successfully - update slot state
            try:
                self.tool_changer.setSlotNotAvailable(slot_id)
            except Exception as e:
                import traceback
                traceback.print_exc()
                return False, f"Failed to update slot state: {str(e)}"

            self.current_gripper = None
            return True, None

    # ----------------------
    # Helper methods
    # ----------------------
    def _get_pickup_positions_and_config(self, gripper_id):
        """Return the pickup positions and configuration for a given gripper."""
        cfg = None
        positions = None
        rcfg = self.robot_service.robot_config

        if gripper_id == 0:
            cfg = rcfg.getSlot0PickupConfig()
            positions = rcfg.getSlot0PickupPointsParsed()
        elif gripper_id == 1:
            cfg = rcfg.getSlot1PickupConfig()
            positions = rcfg.getSlot1PickupPointsParsed()
        elif gripper_id == 4:
            cfg = rcfg.getSlot4PickupConfig()
            positions = rcfg.getSlot4PickupPointsParsed()
        return positions, cfg

    def _get_dropoff_positions_and_config(self, gripper_id):
        """Return the dropoff positions and configuration for a given gripper."""
        cfg = None
        positions = None
        rcfg = self.robot_service.robot_config

        if gripper_id == 0:
            cfg = rcfg.getSlot0DropoffConfig()
            positions = rcfg.getSlot0DropoffPointsParsed()
        elif gripper_id == 1:
            cfg = rcfg.getSlot1DropoffConfig()
            positions = rcfg.getSlot1DropoffPointsParsed()
        elif gripper_id == 4:
            cfg = rcfg.getSlot4DropoffConfig()
            positions = rcfg.getSlot4DropoffPointsParsed()
        return positions, cfg
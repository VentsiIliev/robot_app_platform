from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class MotorState:
    """Represents the state of a motor including its health and error information."""

    address: int
    is_healthy: bool = False
    errors: List[int] = None
    error_count: int = 0
    modbus_errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.modbus_errors is None:
            self.modbus_errors = []

    def add_error(self, error_code: int) -> None:
        """Add an error code to the motor state."""
        if error_code not in self.errors:
            self.errors.append(error_code)
            self.error_count = len(self.errors)
            self.is_healthy = False

    def add_modbus_error(self, error: str) -> None:
        """Add a modbus error to the motor state."""
        self.modbus_errors.append(error)
        self.is_healthy = False

    def clear_errors(self) -> None:
        """Clear all errors and mark motor as healthy."""
        self.errors.clear()
        self.modbus_errors.clear()
        self.error_count = 0
        self.is_healthy = True

    def has_errors(self) -> bool:
        """Check if motor has any errors."""
        return len(self.errors) > 0 or len(self.modbus_errors) > 0

    def get_filtered_errors(self) -> List[int]:
        """Get errors filtered by motor address prefix."""
        motor_address_to_prefix = {
            0: 1,  # Motor 0 errors start with 1x
            2: 2,  # Motor 2 errors start with 2x
            4: 3,  # Motor 4 errors start with 3x
            6: 4  # Motor 6 errors start with 4x
        }

        expected_prefix = motor_address_to_prefix.get(self.address)
        if expected_prefix is None:
            return self.errors

        filtered = []
        for error in self.errors:
            if error == 0:
                continue
            error_prefix = error // 10
            if error_prefix == expected_prefix:
                filtered.append(error)

        return filtered

    def to_dict(self) -> Dict:
        """Convert motor state to dictionary format for backward compatibility."""
        return {
            'state': self.is_healthy,
            'errors': self.get_filtered_errors(),
            'error_count': len(self.get_filtered_errors()),
            'modbus_errors': self.modbus_errors
        }

    def __str__(self) -> str:
        """String representation of motor state."""
        filtered_errors = self.get_filtered_errors()
        return (f"Motor {self.address}: "
                f"Healthy={self.is_healthy}, "
                f"Error Count={len(filtered_errors)}, "
                f"Errors={filtered_errors}")


@dataclass
class AllMotorsState:
    """Represents the state of all motors."""

    success: bool
    motors: Dict[int, MotorState]
    sorted_errors: List[Tuple[int, int]] = None  # (error_code, motor_address)

    def __post_init__(self):
        if self.sorted_errors is None:
            self.sorted_errors = []

    def add_motor_state(self, motor_state: MotorState) -> None:
        """Add a motor state to the collection."""
        self.motors[motor_state.address] = motor_state

    def get_all_errors_sorted(self) -> List[Tuple[int, int]]:
        """Get all errors from all motors sorted by error code."""
        all_errors = []
        for motor_state in self.motors.values():
            filtered_errors = motor_state.get_filtered_errors()
            for error in filtered_errors:
                all_errors.append((error, motor_state.address))

        all_errors.sort(key=lambda x: x[0])
        self.sorted_errors = all_errors
        return all_errors

    def to_dict(self) -> Dict:
        """Convert to dictionary format for backward compatibility."""
        return {
            'success': self.success,
            'motors': {addr: motor.to_dict() for addr, motor in self.motors.items()},
            'sorted_errors': self.get_all_errors_sorted()
        }


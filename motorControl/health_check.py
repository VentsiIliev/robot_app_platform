import time
from typing import List

from applications.glue_dispensing_application.services.glueSprayService.motorControl.error_handler import \
    MotorControlErrorHandler
from applications.glue_dispensing_application.services.glueSprayService.motorControl.motor_state import MotorState, \
    AllMotorsState
from modules.utils.custom_logging import log_if_enabled, LoggingLevel


class HealthCheck:
    def __init__(self,health_check_register,health_check_delay,motor_register_start,motor_error_count_register,logging_enabled,logger):
        self.health_check_register = health_check_register
        self.health_check_delay = health_check_delay
        self.logging_enabled = logging_enabled
        self.motor_error_count_register = motor_error_count_register
        self.motor_register_start = motor_register_start
        self.logger = logger

    def health_check_motor(self, client, motor_address: int, filter_by_motor: bool = True) -> MotorState:
        """Perform health check for a single motor and return MotorState object."""
        ENABLE_LOGGING = self.logging_enabled
        motor_control_logger = self.logger
        HEALTH_CHECK_TRIGGER_REGISTER = self.health_check_register
        DEFAULT_HEALTH_CHECK_DELAY = self.health_check_delay
        log_if_enabled(enabled=ENABLE_LOGGING,
                       logger=motor_control_logger,
                       message=f"Performing health check for motor {motor_address}",
                       level=LoggingLevel.INFO,
                       broadcast_to_ui=False)
        motor_state = MotorState(address=motor_address)

        # Reset motor (acknowledge command)
        modbus_error = client.writeRegisters(HEALTH_CHECK_TRIGGER_REGISTER, [1])
        if modbus_error is not None:
            error_msg = f"Failed to trigger health check: {modbus_error}"
            motor_state.add_modbus_error(error_msg)
            MotorControlErrorHandler.handle_modbus_error(HEALTH_CHECK_TRIGGER_REGISTER, modbus_error)
            return motor_state

        log_if_enabled(enabled=ENABLE_LOGGING,
                       logger=motor_control_logger,
                       message=f"Health check triggered, waiting for {DEFAULT_HEALTH_CHECK_DELAY} seconds",
                       level=LoggingLevel.INFO,
                       broadcast_to_ui=False)
        time.sleep(DEFAULT_HEALTH_CHECK_DELAY)

        # Check for motor-specific errors
        error_check_result, motor_errors_count = self._get_motor_errors_count(client, motor_address)

        if not error_check_result:
            motor_state.add_modbus_error("Failed to read motor error count")
            return motor_state

        if motor_errors_count > 0:
            raw_motor_errors = self._read_errors(client, motor_errors_count)
            if raw_motor_errors:
                # Add all non-zero errors to motor state
                for error in raw_motor_errors:
                    if error != 0:
                        motor_state.add_error(error)

                # Get filtered errors for this specific motor
                filtered_errors = motor_state.get_filtered_errors()

                if filtered_errors:
                    log_if_enabled(enabled=ENABLE_LOGGING,
                                   logger=motor_control_logger,
                                   message=f"Motor {motor_address} has errors: {filtered_errors}",
                                   level=LoggingLevel.WARNING,
                                   broadcast_to_ui=False)
                    MotorControlErrorHandler.handle_motor_errors(motor_address, filtered_errors)
                    motor_state.is_healthy = False
                else:
                    log_if_enabled(enabled=ENABLE_LOGGING,
                                   logger=motor_control_logger,
                                   message=f"Motor {motor_address} has no relevant errors",
                                   level=LoggingLevel.INFO,
                                   broadcast_to_ui=False)
                    motor_state.is_healthy = True
            else:
                motor_state.add_modbus_error("Failed to read error values")
        else:
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Motor {motor_address} has no errors",
                           level=LoggingLevel.INFO,
                           broadcast_to_ui=False)
            motor_state.is_healthy = True

        return motor_state

    def health_check_all_motors(self, client, motor_addresses: List[int]) -> AllMotorsState:
        """Perform health check for all motors efficiently."""
        HEALTH_CHECK_TRIGGER_REGISTER = self.health_check_register
        ENABLE_LOGGING = self.logging_enabled
        motor_control_logger = self.logger
        DEFAULT_HEALTH_CHECK_DELAY = self.health_check_delay
        all_motors_state = AllMotorsState(success=True, motors={})

        # Trigger health check once for all motors
        modbus_error = client.writeRegisters(HEALTH_CHECK_TRIGGER_REGISTER, [1])
        if modbus_error is not None:
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Failed to trigger health check: {modbus_error}",
                           level=LoggingLevel.ERROR,
                           broadcast_to_ui=False)
            MotorControlErrorHandler.handle_modbus_error(HEALTH_CHECK_TRIGGER_REGISTER, modbus_error)
            all_motors_state.success = False
            # Create failed motor states for all motors
            for motor_address in motor_addresses:
                motor_state = MotorState(address=motor_address)
                motor_state.add_modbus_error("Failed to trigger health check")
                all_motors_state.add_motor_state(motor_state)
            return all_motors_state

        log_if_enabled(enabled=ENABLE_LOGGING,
                       logger=motor_control_logger,
                       message=f"Health check triggered for all motors, waiting {DEFAULT_HEALTH_CHECK_DELAY} seconds",
                       level=LoggingLevel.INFO,
                       broadcast_to_ui=False)
        time.sleep(DEFAULT_HEALTH_CHECK_DELAY)

        # Get global error count
        error_check_result, global_errors_count = self._get_motor_errors_count(client)

        if not error_check_result:
            # Communication failed - mark all motors as unhealthy
            all_motors_state.success = False
            for motor_address in motor_addresses:
                motor_state = MotorState(address=motor_address)
                motor_state.add_modbus_error("Failed to communicate with motor controller")
                all_motors_state.add_motor_state(motor_state)
                log_if_enabled(enabled=ENABLE_LOGGING,
                               logger=motor_control_logger,
                               message=f"Motor {motor_address} communication failed - marked as unhealthy",
                               level=LoggingLevel.ERROR,
                               broadcast_to_ui=False)
        elif global_errors_count == 0:
            # Communication successful but no errors - set all motors to healthy state
            for motor_address in motor_addresses:
                motor_state = MotorState(address=motor_address, is_healthy=True)
                all_motors_state.add_motor_state(motor_state)
                log_if_enabled(enabled=ENABLE_LOGGING,
                               logger=motor_control_logger,
                               message=f"Motor {motor_address} has no errors",
                               level=LoggingLevel.INFO,
                               broadcast_to_ui=False)
        else:
            # Read all errors once
            raw_motor_errors = self._read_errors(client, global_errors_count)
            if raw_motor_errors:
                # Filter non-zero errors
                all_motor_errors = [err for err in raw_motor_errors if err != 0]

                # Process each motor
                for motor_address in motor_addresses:
                    motor_state = MotorState(address=motor_address)

                    # Add all errors to motor state (filtering will be done by MotorState)
                    for error in all_motor_errors:
                        motor_state.add_error(error)

                    # Check if motor has relevant errors
                    filtered_errors = motor_state.get_filtered_errors()

                    if filtered_errors:
                        log_if_enabled(enabled=ENABLE_LOGGING,
                                       logger=motor_control_logger,
                                       message=f"Motor {motor_address} has errors: {filtered_errors}",
                                       level=LoggingLevel.WARNING,
                                       broadcast_to_ui=False)
                        MotorControlErrorHandler.handle_motor_errors(motor_address, filtered_errors,ENABLE_LOGGING,motor_control_logger)
                        motor_state.is_healthy = False
                    else:
                        log_if_enabled(enabled=ENABLE_LOGGING,
                                       logger=motor_control_logger,
                                       message=f"Motor {motor_address} has no relevant errors",
                                       level=LoggingLevel.INFO,
                                       broadcast_to_ui=False)
                        motor_state.is_healthy = True

                    all_motors_state.add_motor_state(motor_state)
            else:
                # Failed to read errors, mark all motors as failed
                all_motors_state.success = False
                for motor_address in motor_addresses:
                    motor_state = MotorState(address=motor_address)
                    motor_state.add_modbus_error("Failed to read error values")
                    all_motors_state.add_motor_state(motor_state)

        return all_motors_state

    def _read_errors(self, client, errors_count):
        """Read motor error values from error registers"""
        MOTOR_ERROR_REGISTERS_START = self.motor_register_start
        HEALTH_CHECK_TRIGGER_REGISTER = self.health_check_register
        ENABLE_LOGGING = self.logging_enabled
        motor_control_logger = self.logger
        DEFAULT_HEALTH_CHECK_DELAY = self.health_check_delay
        error_values, modbus_error = client.readRegisters(MOTOR_ERROR_REGISTERS_START, errors_count)

        if modbus_error is not None:
            MotorControlErrorHandler.handle_modbus_error("error_registers", modbus_error)
            return []

        if not error_values:
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message="No errors read from motor",
                           level=LoggingLevel.INFO,
                           broadcast_to_ui=False)
            return []

        return error_values

    def _get_motor_errors_count(self, client, motor_address=None):
        """Read motor errors count from register 20"""
        MOTOR_ERROR_COUNT_REGISTER = self.motor_error_count_register
        ENABLE_LOGGING = self.logging_enabled
        motor_control_logger = self.logger
        try:
            errors_count, modbus_error = client.read(MOTOR_ERROR_COUNT_REGISTER)

            if modbus_error is not None:
                MotorControlErrorHandler.handle_modbus_error(f"{motor_address}_error_count", modbus_error)
                return False, None

            return True, errors_count

        except Exception as e:
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Exception reading motor {motor_address} errors count: {e}",
                           level=LoggingLevel.ERROR,
                           broadcast_to_ui=False)
            return False, None

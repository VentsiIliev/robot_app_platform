import time

from applications.glue_dispensing_application.services.glueSprayService.motorControl.error_handler import \
    MotorControlErrorHandler
from applications.glue_dispensing_application.services.glueSprayService.motorControl.health_check import HealthCheck
from applications.glue_dispensing_application.services.glueSprayService.motorControl.motor_state import MotorState, \
    AllMotorsState
from applications.glue_dispensing_application.services.glueSprayService.motorControl.utils import split_into_16bit
from modules.modbusCommunication import ModbusController
from modules.utils.custom_logging import LoggingLevel, log_if_enabled, setup_logger

ENABLE_LOGGING = True
motor_control_logger = setup_logger("MotorControl")

# Motor Control Register Constants
HEALTH_CHECK_TRIGGER_REGISTER = 17
MOTOR_ERROR_COUNT_REGISTER = 20
MOTOR_ERROR_REGISTERS_START = 21

# Motor Control Configuration
DEFAULT_RAMP_STEPS = 1
DEFAULT_HEALTH_CHECK_DELAY = 3  # seconds
DEFAULT_RAMP_STEP_DELAY = 0.001  # seconds

class MotorControl(ModbusController):
    def __init__(self,motorSlaveId=1):
        super().__init__()
        self.motorsId = motorSlaveId
        self.healthCheck = HealthCheck(
            health_check_register=HEALTH_CHECK_TRIGGER_REGISTER,
            health_check_delay= DEFAULT_HEALTH_CHECK_DELAY,
            motor_register_start=MOTOR_ERROR_REGISTERS_START,
            motor_error_count_register=MOTOR_ERROR_COUNT_REGISTER,
            logging_enabled=ENABLE_LOGGING,
            logger=motor_control_logger
        )
        # Connection reuse for adjustMotorSpeed
        self._adjust_client = None
        self._adjust_client_connected = False

    def adjustMotorSpeed(self, motorAddress, speed):
        speed = int(speed)
        # print(f"adjustMotorSpeed {speed}")
        
        # Check if we have a reusable connection
        if self._adjust_client is None or not self._adjust_client_connected:
            try:
                self._adjust_client = self.getModbusClient(self.motorsId)
                self._adjust_client_connected = True
                log_if_enabled(enabled=ENABLE_LOGGING,
                              logger=motor_control_logger,
                              message="Created new adjust client connection",
                              level=LoggingLevel.INFO,
                              broadcast_to_ui=False)
            except Exception as e:
                log_if_enabled(enabled=ENABLE_LOGGING,
                              logger=motor_control_logger,
                              message=f"Failed to create adjust client: {e}",
                              level=LoggingLevel.ERROR,
                              broadcast_to_ui=False)
                return False
        
        try:
            # high16, low16 = split_into_16bit(speed)
            # high16_int, low16_int = int(high16, 16), int(low16, 16)
            result, errors = self._ramp_motor(value=speed,
                             steps=1,
                             client=self._adjust_client,
                             motorAddress=motorAddress)
            # result,errors = self._write_motor_register(self._adjust_client, motorAddress, low16_int, high16_int)
            
            if not result:
                log_if_enabled(enabled=ENABLE_LOGGING,
                               logger=motor_control_logger,
                               message=f"Failed to adjust motor {motorAddress} to {speed}. Errors: {errors}",
                               level=LoggingLevel.ERROR,
                               broadcast_to_ui=False)
            else:
                # print(f"Motor {motorAddress} adjusted to speed {speed} (High16={high16_int}, Low16={low16_int})")
                log_if_enabled(enabled=ENABLE_LOGGING,
                               logger=motor_control_logger,
                               message=f"Motor {motorAddress} adjusted to speed {speed})",
                               level=LoggingLevel.INFO,
                               broadcast_to_ui=False)
            
            return result
            
        except Exception as e:
            # Connection error - reset connection state and retry once
            log_if_enabled(enabled=ENABLE_LOGGING,
                          logger=motor_control_logger,
                          message=f"Connection error in adjustMotorSpeed: {e}. Resetting connection.",
                          level=LoggingLevel.WARNING,
                          broadcast_to_ui=False)
            self._adjust_client_connected = False
            self._adjust_client = None
            return False

    def closeAdjustConnection(self):
        """Manually close the adjust motor speed connection."""
        if self._adjust_client is not None and self._adjust_client_connected:
            try:
                self._adjust_client.close()
                log_if_enabled(enabled=ENABLE_LOGGING,
                              logger=motor_control_logger,
                              message="Closed adjust client connection",
                              level=LoggingLevel.INFO,
                              broadcast_to_ui=False)
            except Exception as e:
                log_if_enabled(enabled=ENABLE_LOGGING,
                              logger=motor_control_logger,
                              message=f"Error closing adjust client: {e}",
                              level=LoggingLevel.WARNING,
                              broadcast_to_ui=False)
            finally:
                self._adjust_client = None
                self._adjust_client_connected = False

    def motorOn(self, motorAddress, speed, ramp_steps, initial_ramp_speed, initial_ramp_speed_duration):
        t_total_start = time.perf_counter()
        # initialize durations
        dur_get_client = dur_ramp = dur_sleep = dur_split = dur_write = dur_close = 0.0

        # speed = int(-speed)
        speed = int(speed)
        # initial_ramp_speed = int(-initial_ramp_speed)
        initial_ramp_speed = int(initial_ramp_speed)

        log_if_enabled(enabled=ENABLE_LOGGING,
                       logger=motor_control_logger,
                       message=f"""MotorControl.motorOn called with
          motorAddress: {motorAddress}
          speed: {speed}
          ramp_steps: {ramp_steps}
          initial_ramp_speed: {initial_ramp_speed}
          initial_ramp_speed_duration: {initial_ramp_speed_duration}""",
                       level=LoggingLevel.INFO,
                       broadcast_to_ui=False)

        result = False
        try:
            t = time.perf_counter()
            client = self.getModbusClient(self.motorsId)
            dur_get_client = time.perf_counter() - t

            t = time.perf_counter()
            result, errors = self._ramp_motor(initial_ramp_speed, ramp_steps, client, motorAddress)
            dur_ramp = time.perf_counter() - t
            if not result:
                log_if_enabled(enabled=ENABLE_LOGGING,
                               logger=motor_control_logger,
                               message=f"Failed to ramp motor {motorAddress}. Errors: {errors}",
                               level=LoggingLevel.ERROR,
                               broadcast_to_ui=False)
            else:
                log_if_enabled(enabled=ENABLE_LOGGING,
                               logger=motor_control_logger,
                               message=f"Motor ramped to speed: {initial_ramp_speed}",
                               level=LoggingLevel.INFO,
                               broadcast_to_ui=False)

            t = time.perf_counter()
            time.sleep(initial_ramp_speed_duration)
            dur_sleep = time.perf_counter() - t

            t = time.perf_counter()
            high16, low16 = split_into_16bit(speed)
            high16_int, low16_int = int(high16, 16), int(low16, 16)
            dur_split = time.perf_counter() - t

            t = time.perf_counter()
            result, errors = self._write_motor_register(client, motorAddress, low16_int,
                                                        high16_int)
            dur_write = time.perf_counter() - t
            if not result:
                log_if_enabled(enabled=ENABLE_LOGGING,
                               logger=motor_control_logger,
                               message=f"Failed to set motor {motorAddress} to {int(speed / 2)}. Errors: {errors}",
                               level=LoggingLevel.ERROR,
                               broadcast_to_ui=False)
            else:
                log_if_enabled(enabled=ENABLE_LOGGING,
                               logger=motor_control_logger,
                               message=f"Motor {motorAddress} set to speed {speed} (High16={high16_int}, Low16={low16_int})",
                               level=LoggingLevel.INFO,
                               broadcast_to_ui=False)

            t = time.perf_counter()
            client.close()
            dur_close = time.perf_counter() - t

        except Exception as e:
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Error turning on motor {motorAddress}: {e}",
                           level=LoggingLevel.ERROR,
                           broadcast_to_ui=False)
        finally:
            t_total_end = time.perf_counter()
            total = t_total_end - t_total_start
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Timing breakdown (seconds): get_client={dur_get_client:.6f}, ramp={dur_ramp:.6f}, sleep={dur_sleep:.6f}, split={dur_split:.6f}, write={dur_write:.6f}, close={dur_close:.6f}, total={total:.6f}",
                           level=LoggingLevel.INFO,
                           broadcast_to_ui=False)

        return result



    def motorOff(self, motorAddress, speedReverse, reverse_time,ramp_steps):
        speedReverse = -speedReverse
        log_if_enabled(enabled=ENABLE_LOGGING,
                       logger=motor_control_logger,
                       message=f"MotorControl.motorOff called with speedReverse: {speedReverse}, motorAddress: {motorAddress}, reverse_time: {reverse_time}, ramp_steps: {ramp_steps}",
                       level=LoggingLevel.INFO,
                       broadcast_to_ui=False)

        result = False
        try:
            client = self.getModbusClient(self.motorsId)

            # Initial stop - check for modbus errors
            modbus_error = client.writeRegisters(motorAddress, [0, 0])
            if modbus_error is not None:
                MotorControlErrorHandler.handle_modbus_error(motorAddress, modbus_error,ENABLE_LOGGING,motor_control_logger)
                client.close()
                return False

            result, errors = self._ramp_motor(speedReverse, ramp_steps, client, motorAddress)
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Motor reverse time = {reverse_time} seconds",
                           level=LoggingLevel.INFO,
                           broadcast_to_ui=False)

            time.sleep(reverse_time)  # Wait for the motor to stop complete reverse movement
            
            # Final stop - check for modbus errors
            modbus_error = client.writeRegisters(motorAddress, [0, 0])
            if modbus_error is not None:
                MotorControlErrorHandler.handle_modbus_error(motorAddress, modbus_error,ENABLE_LOGGING,motor_control_logger)
                result = False
                
            client.close()

        except Exception as e:
            import traceback
            traceback.print_exc()
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Error turning off motor {motorAddress}: {e}",
                           level=LoggingLevel.ERROR,
                           broadcast_to_ui=False)
        return result



    def motorState(self, motor_address) -> MotorState:
        """Get single motor state as MotorState object."""
        try:
            client = self.getModbusClient(self.motorsId)
            motor_state = self.healthCheck.health_check_motor(client, motor_address)
            client.close()
            return motor_state
        except Exception as e:
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Exception reading motor {motor_address} state: {e}",
                           level=LoggingLevel.ERROR,
                           broadcast_to_ui=False)
            error_state = MotorState(address=motor_address)
            error_state.add_modbus_error(f"Exception: {str(e)}")
            return error_state

    def getAllMotorStates(self) -> AllMotorsState:
        """Get all motor states at once using new MotorState objects.
        Reads error counts, then reads and sorts errors by error codes for all motors.
        
        Returns:
            AllMotorsState: Object containing all motor states with sorted errors
        """
        motor_addresses = [0, 2, 4, 6]
        
        try:
            client = self.getModbusClient(self.motorsId)
            all_motors_state = self.healthCheck.health_check_all_motors(client, motor_addresses)
            client.close()
            return all_motors_state
            
        except Exception as e:
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Exception in getAllMotorStates: {e}",
                           level=LoggingLevel.ERROR,
                           broadcast_to_ui=False)
            # Create failed state for all motors
            failed_state = AllMotorsState(success=False, motors={})
            for motor_address in motor_addresses:
                motor_state = MotorState(address=motor_address)
                motor_state.add_modbus_error(f"Exception: {str(e)}")
                failed_state.add_motor_state(motor_state)
            return failed_state



    def _write_motor_register(self, client, motorAddress, low16_int, high16_int):
        modbus_errors = []
        motor_errors = []
        
        # Attempt to write to the motor register
        modbus_error = client.writeRegisters(motorAddress, [low16_int, high16_int])

        if modbus_error is not None:
            MotorControlErrorHandler.handle_modbus_error(motorAddress, modbus_error,ENABLE_LOGGING,motor_control_logger)
            modbus_errors.append(modbus_error)
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Modbus Error after writing to motor {motorAddress}: {modbus_error}",
                           level=LoggingLevel.ERROR,
                           broadcast_to_ui=False)
            return False, {"modbus_errors": modbus_errors, "motor_errors": motor_errors}
        
        return True, {"modbus_errors": modbus_errors, "motor_errors": motor_errors}



    def _ramp_motor(self, value, steps, client, motorAddress):
        # print("Ramping value to:", value)
        increment = int(value / steps)
        if steps == 1:
            increment = int(value)
        value = 0
        errors = []
        result = True

        # Timers
        t_start = time.perf_counter()
        dur_split_total = 0.0
        dur_write_total = 0.0
        dur_step_total = 0.0

        for i in range(steps):
            step_start = time.perf_counter()

            value = increment * (i + 1)

            t = time.perf_counter()
            high16, low16 = split_into_16bit(value)
            high16_int, low16_int = int(high16, 16), int(low16, 16)
            dur_split = time.perf_counter() - t
            dur_split_total += dur_split

            t = time.perf_counter()
            result, errors = self._write_motor_register(client, motorAddress, low16_int, high16_int)
            # time.sleep(0.02)
            dur_write = time.perf_counter() - t
            dur_write_total += dur_write

            if not result:
                log_if_enabled(enabled=ENABLE_LOGGING,
                               logger=motor_control_logger,
                               message=f"Failed to write to motor register at step {i + 1}. Errors: {errors}",
                               level=LoggingLevel.ERROR,
                               broadcast_to_ui=False)
                dur_step_total += time.perf_counter() - step_start
                result = False
                break

            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Ramped to step {i + 1}/{steps}: Value={value} (High16={high16_int}, Low16={low16_int})",
                           level=LoggingLevel.INFO,
                           broadcast_to_ui=False)
            # time.sleep(DEFAULT_RAMP_STEP_DELAY)

            dur_step_total += time.perf_counter() - step_start

        total_time = time.perf_counter() - t_start
        log_if_enabled(enabled=ENABLE_LOGGING,
                       logger=motor_control_logger,
                       message=f"Ramping timing breakdown (seconds): split_total={dur_split_total:.6f}, write_total={dur_write_total:.6f}, steps_total={dur_step_total:.6f}, total={total_time:.6f}",
                       level=LoggingLevel.INFO,
                       broadcast_to_ui=False)

        return result, errors



if __name__ == "__main__":
    motorControl = MotorControl()
    speedTemp = 10000
    speedReverseTemp = 250

    while True:
        try:
            motorAddressTemp = int(input("Enter motor address (-1/0/2/4/6 or 'exit' to quit): ").strip())
        except ValueError:
            print("Exiting.")
            break

        while True:
            command = input(f"Enter command for motor {motorAddressTemp} (on/off/state/newstate/allstates/back): ").strip().lower()
            if command == "on":
                motorControl.motorOn(motorAddressTemp, speedTemp,3,22000,1)
            elif command == "off":
                motorControl.motorOff(motorAddressTemp, speedReverseTemp, reverse_time=0.5,ramp_steps=1)
            elif command == "state":
                motorControl.motorState(motorAddressTemp)
            elif command == "newstate":
                motor_state = motorControl.motorState(motorAddressTemp)
                print("New Motor State Object:")
                print(f"  {motor_state}")
                print(f"  Modbus Errors: {motor_state.modbus_errors}")
            elif command == "allstates":
                all_motors_state = motorControl.getAllMotorStates()
                print("All Motor States (New Format):")
                print(f"Success: {all_motors_state.success}")
                for motor_addr, motor_state in all_motors_state.motors.items():
                    print(f"  {motor_state}")
                sorted_errors = all_motors_state.get_all_errors_sorted()
                print(f"Sorted Errors: {sorted_errors}")

            elif command == "back":
                break
            else:
                print("Unknown command. Please enter 'on', 'off', 'state', 'newstate', 'allstates', or 'back'.")





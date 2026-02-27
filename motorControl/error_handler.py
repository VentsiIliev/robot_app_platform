from applications.glue_dispensing_application.services.glueSprayService.motorControl.errorCodes import MotorErrorCode
from modules.utils.custom_logging import log_if_enabled, LoggingLevel


class MotorControlErrorHandler:
    @staticmethod
    def handle_modbus_error(motorAddress, modbus_error,enable_logging,logger):
        ENABLE_LOGGING = enable_logging
        motor_control_logger = logger
        log_if_enabled(enabled=ENABLE_LOGGING,
                       logger=motor_control_logger,
                       message="Handling Modbus error...",
                       level=LoggingLevel.WARNING,
                       broadcast_to_ui=False)
        if modbus_error is not None:
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Modbus error for motor {motorAddress} - {modbus_error.name}: {modbus_error.description()}",
                           level=LoggingLevel.ERROR,
                           broadcast_to_ui=False)
        else:
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"No Modbus error for motor {motorAddress}",
                           level=LoggingLevel.INFO,
                           broadcast_to_ui=False)

    @staticmethod
    def handle_motor_errors(motorAddress, errors,enable_logging,logger):
        ENABLE_LOGGING = enable_logging
        motor_control_logger = logger
        # print("Handling motor-specific errors...")
        if errors:
            # print(f"Motor {motorAddress} has the following errors:")
            for error in errors:
                try:
                    error_code = MotorErrorCode(error)
                    log_if_enabled(enabled=ENABLE_LOGGING,
                                   logger=motor_control_logger,
                                   message=f"Motor error code: {error_code.name} ({error_code.value}) - {error_code.description()}",
                                   level=LoggingLevel.WARNING,
                                   broadcast_to_ui=False)
                except ValueError:
                    log_if_enabled(enabled=ENABLE_LOGGING,
                                   logger=motor_control_logger,
                                   message=f"Unknown motor error code: {error} (not a recognized motor error)",
                                   level=LoggingLevel.WARNING,
                                   broadcast_to_ui=False)
        else:
            log_if_enabled(enabled=ENABLE_LOGGING,
                           logger=motor_control_logger,
                           message=f"Motor {motorAddress} has no errors",
                           level=LoggingLevel.INFO,
                           broadcast_to_ui=False)

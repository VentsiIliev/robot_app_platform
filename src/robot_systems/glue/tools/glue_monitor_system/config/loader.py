import inspect
import logging
from pathlib import Path
from modules.shared.tools.glue_monitor_system.config.validator import (
    ConfigValidator, GlueMonitorConfig, ConfigurationError
)
from modules.utils.custom_logging import LoggingLevel, ColoredFormatter


# Global logger variable
ENABLE_LOGGING = False  # Enable or disable logging

# Initialize logger if enabled
if ENABLE_LOGGING:
    glue_cell_logger = logging.getLogger('glue_cell')
    glue_cell_logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    for handler in glue_cell_logger.handlers[:]:
        glue_cell_logger.removeHandler(handler)

    # Create console handler with custom formatter
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # Custom format with function name and values
    formatter = ColoredFormatter(
        '[%(asctime)s] [%(levelname)s] [%(funcName)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    glue_cell_logger.addHandler(console_handler)

    # Prevent propagation to root logger
    glue_cell_logger.propagate = False
else:
    glue_cell_logger = None


def log_if_enabled(level, message):
    """Helper function to log only if logging is enabled"""
    if ENABLE_LOGGING and glue_cell_logger:
        # Get the calling function's name
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name

        # Convert LoggingLevel enum to string if necessary
        if isinstance(level, LoggingLevel):
            level_name = level.name.lower()
        else:
            level_name = level

        # Create a temporary log record with the caller's function name
        log_method = getattr(glue_cell_logger, level_name)

        # Temporarily modify the logger to show the actual caller
        original_findCaller = glue_cell_logger.findCaller

        def mock_findCaller(stack_info=False, stacklevel=1):
            # Return the caller's info instead of log_if_enabled
            return (caller_frame.f_code.co_filename, caller_frame.f_lineno, caller_name, None)

        glue_cell_logger.findCaller = mock_findCaller
        try:
            log_method(message)
        finally:
            # Restore original findCaller
            glue_cell_logger.findCaller = original_findCaller


def load_config(path: Path) -> GlueMonitorConfig:
    """Load and validate configuration from a JSON file with strict validation."""
    try:
        return ConfigValidator.validate_and_load(path)
    except ConfigurationError as e:
        raise RuntimeError(f"Configuration validation failed: {e}") from e


# Endpoint templates for backward compatibility
TARE_ENDPOINT = "/tare?loadCellId={current_cell}"
GET_CONFIG_ENDPOINT = "/get-config?loadCellId={current_cell}"
UPDATE_OFFSET_ENDPOINT = "/update-config?loadCellId={current_cell}&offset={offset}"
UPDATE_SCALE_ENDPOINT = "/update-config?loadCellId={current_cell}&scale={scale}"
UPDATE_CONFIG_ENDPOINT = "/update-config?loadCellId={current_cell}&offset={offset}&scale={scale}"


from modules.shared.tools.glue_monitor_system.config.loader import log_if_enabled
from modules.utils.custom_logging import LoggingLevel


def handle_connection_error(url,weights):
    log_if_enabled(LoggingLevel.ERROR, f"🔴 CONNECTION ERROR: Network unreachable or service down at {url}")
    log_if_enabled(LoggingLevel.WARNING, "Setting all weights to 0.0g due to connection failure")
    # Set weights to 0 when connection fails
    weights[0] = weights[1] = weights[2] = 0.0
    # Additional error handling logic can be added here

def handle_timeout(url,fetchTimeout):
    log_if_enabled(LoggingLevel.WARNING,
                   f"⏱️  TIMEOUT: Request to {url} took longer than {fetchTimeout}s")
    log_if_enabled(LoggingLevel.DEBUG, "Keeping previous weight values during timeout")
    # Keep previous values on timeout

def handle_HTTPError(error,url,weights):
    log_if_enabled(LoggingLevel.ERROR,
                   f"🔴 HTTP ERROR: {error.response.status_code} - {error.response.reason} from {url}")
    log_if_enabled(LoggingLevel.WARNING, "Setting all weights to 0.0g due to server error")
    # Set weights to 0 when server returns error
    weights[0] = weights[1] = weights[2] = 0.0

def handle_JSONDecodeError(url):
    log_if_enabled(LoggingLevel.ERROR, f"🔴 JSON ERROR: Invalid response format from {url}")
    log_if_enabled(LoggingLevel.DEBUG, "Keeping previous weight values during parsing error")
    # Keep previous values on parsing error

def handle_value_error(error):
    log_if_enabled(LoggingLevel.ERROR, f"🔴 VALUE ERROR: Unable to convert weight values to float - {error}")
    log_if_enabled(LoggingLevel.DEBUG, "Keeping previous weight values during conversion error")
    # Keep previous values on conversion error

def handle_generic_exception(error):
    log_if_enabled(LoggingLevel.CRITICAL, f"🔴 UNEXPECTED ERROR: An unexpected error occurred - {error}")
    log_if_enabled(LoggingLevel.DEBUG, "Keeping previous weight values during unexpected error")
    # Keep previous values on unexpected error
# Full path to config inside storage - use application-specific storage
import json
import threading
import time
from pathlib import Path

import requests

from communication_layer.api.v1.topics import GlueCellTopics
from modules.shared.MessageBroker import MessageBroker
from modules.shared.tools.glue_monitor_system.config.loader import log_if_enabled, load_config
from modules.utils import PathResolver
from modules.utils.custom_logging import LoggingLevel
from core.application.ApplicationStorageResolver import get_app_settings_path
from modules.shared.tools.glue_monitor_system.testing import mocks
from modules.shared.tools.glue_monitor_system.utils import errors

def _get_glue_config_path():
    """Get the path to glue cell config using application-specific storage."""
    try:
        return Path(get_app_settings_path("glue_dispensing_application", "glue_cell_config"))
    except ImportError:
        import traceback
        traceback.print_exc()
        # Fallback to old path for backward compatibility
        return Path(PathResolver.get_settings_file_path('glue_cell_config.json'))

config_path = _get_glue_config_path()

class GlueDataFetcher:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(GlueDataFetcher, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent reinitialization on subsequent instantiations
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.weight1 = 0
        self.weight2 = 0
        self.weight3 = 0

        # Initialize MessageBroker first
        self.broker = MessageBroker()

        # Initialize state management
        from modules.shared.tools.glue_monitor_system.core.state_machine import (
            StateManager, MessageBrokerStatePublisher, StateMonitor, CellState
        )

        publisher = MessageBrokerStatePublisher(self.broker)
        self.state_manager = StateManager(publisher)
        self.state_monitor = StateMonitor(self.state_manager)

        # Initialize cells to INITIALIZING state (valid transition from UNKNOWN)
        for cell_id in [1, 2, 3]:
            self.state_manager.transition_cell_to(
                cell_id=cell_id,
                new_state=CellState.INITIALIZING,
                reason="Cell initialization started"
            )

        # Load config to determine mode and URL
        try:
            self.config = load_config(config_path)
            if self.config.is_test_mode:
                mock.init_test_mode(self.config)
            else:
                self.setup_production_mode()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.state_monitor.mark_initialization_failed(str(e))
            raise RuntimeError(f"[GlueDataFetcher] Failed to load configuration: {e}") from e

        self.fetchTimeout = self.config.global_settings.fetch_timeout_seconds
        self._stop_thread = threading.Event()
        self.thread = None
        self._initialized = True

    def setup_production_mode(self):
        self.url = f"{self.config.server.base_url}{self.config.endpoints.weights}"
        print(f"[GlueDataFetcher] Running in PRODUCTION mode - using {self.url}")

    def publish_weights(self):
        self.broker.publish(GlueCellTopics.CELL_1_WEIGHT, self.weight1)
        self.broker.publish(GlueCellTopics.CELL_2_WEIGHT, self.weight2)
        self.broker.publish(GlueCellTopics.CELL_3_WEIGHT, self.weight3)

        # print(f"[GlueDataFetcher] Publishing weights: Cell1={self.weight1}g, Cell2={self.weight2}g, Cell3={self.weight3}g")

        # Update state monitoring with new weight values (convert g to kg)
        self.state_monitor.update_cell_weight(1, self.weight1 / 1000.0)
        self.state_monitor.update_cell_weight(2, self.weight2 / 1000.0)
        self.state_monitor.update_cell_weight(3, self.weight3 / 1000.0)

        # Update overall service state based on cell states
        self.state_monitor.update_overall_service_state()

    def unpack_weights(self, weights):
        try:
            self.weight1 = float(weights["weight1"])
            self.weight2 = float(weights["weight2"])
            self.weight3 = float(weights["weight3"])
        except KeyError as e:
            raise ValueError(f"Missing required weight field: {e}") from e
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid weight value: {e}") from e

    def fetch(self):
        log_if_enabled(LoggingLevel.DEBUG, f"Fetching weights from {self.url}")
        try:
            response = requests.get(self.url, timeout=self.fetchTimeout)
            response.raise_for_status()
            weights = json.loads(response.text.strip())

            self.unpack_weights(weights)
            self.publish_weights()

            log_if_enabled(LoggingLevel.DEBUG, f"Raw weights received: {weights}")
            log_if_enabled(LoggingLevel.INFO, f"WEIGHT DATA UPDATED:")
            log_if_enabled(LoggingLevel.INFO, f"  ├─ Weight 1: {self.weight1:.2f}g")
            log_if_enabled(LoggingLevel.INFO, f"  ├─ Weight 2: {self.weight2:.2f}g")
            log_if_enabled(LoggingLevel.INFO, f"  └─ Weight 3: {self.weight3:.2f}g")
            log_if_enabled(LoggingLevel.DEBUG, "Published weights to message broker")

        except requests.exceptions.ConnectionError:
            error_handling.handle_connection_error(self.url,[self.weight1,self.weight2,self.weight3])

        except requests.exceptions.Timeout:
            error_handling.handle_timeout(self.url,self.fetchTimeout)

        except requests.exceptions.HTTPError as e:
            error_handling.handle_HTTPError(e,self.url,[self.weight1,self.weight2,self.weight3])

        except json.JSONDecodeError:
            error_handling.handle_JSONDecodeError(self.url)

        except ValueError as e:
            error_handling.handle_value_error(e)

        except Exception as e:
            error_handling.handle_generic_exception(e)

    def _fetch_loop(self):
        while not self._stop_thread.is_set():
            self.fetch()
            sleep_interval = self.config.global_settings.data_fetch_interval_ms / 1000.0
            time.sleep(sleep_interval)

    def reload_config(self):
        """Reload configuration and restart the fetcher with new settings"""
        print("[GlueDataFetcher] Reloading configuration...")

        # Stop current thread
        was_running = self.thread is not None and self.thread.is_alive()
        if was_running:
            self.stop()

        try:
            self.config = load_config(config_path)
            self.fetchTimeout = self.config.global_settings.fetch_timeout_seconds
            if self.config.is_test_mode:
                self.url = mock.init_test_mode(self.config)
            else:
                self.setup_production_mode()
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"[GlueDataFetcher] Failed to reload configuration: {e}") from e

        # Restart if it was running
        if was_running:
            self.start()

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self._stop_thread.clear()
            self.thread = threading.Thread(target=self._fetch_loop, daemon=True)
            self.thread.start()

            # Mark initialization as complete
            self.state_monitor.mark_initialization_complete()
            print("[GlueDataFetcher] Started successfully, service is READY")

    def stop(self):
        self._stop_thread.set()
        if self.thread is not None:
            self.thread.join()

if __name__ == "__main__":
    fetcher = GlueDataFetcher()
    fetcher.start()

    broker = MessageBroker()
    def print_weight_1(message):
        print(f"Received Weight 1: {message}")
    broker.subscribe(GlueCellTopics.CELL_1_WEIGHT, print_weight_1)

    while True:
        time.sleep(1)  # Keep the main thread alive

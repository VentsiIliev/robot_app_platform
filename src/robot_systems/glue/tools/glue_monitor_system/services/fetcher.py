"""
Non-singleton weight data fetcher implementation with proper dependency injection.
Replaces the singleton-based GlueDataFetcher with a cleaner architecture.
"""
import json
import threading
import time
from typing import Dict, Optional

import requests

from modules.shared.tools.glue_monitor_system.interfaces.protocols import IWeightDataFetcher, IDataPublisher, IConfigurationManager
from modules.shared.tools.glue_monitor_system.config.validator import GlueMonitorConfig
from modules.shared.tools.glue_monitor_system.config.loader import log_if_enabled
from modules.shared.tools.glue_monitor_system.utils import errors
from modules.utils.custom_logging import LoggingLevel


class WeightDataFetcher(IWeightDataFetcher):
    """
    Non-singleton weight data fetcher with proper dependency injection.
    Fetches weight data from configured endpoints and publishes to message broker.
    """
    
    def __init__(self, config_manager: IConfigurationManager, data_publisher: IDataPublisher):
        self._config_manager = config_manager
        self._data_publisher = data_publisher
        self._config: Optional[GlueMonitorConfig] = None
        
        # Current weights
        self._weights: Dict[int, float] = {}
        
        # Threading
        self._stop_thread = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Connection properties
        self.url: Optional[str] = None
        self.fetch_timeout: int = 5
        
        # Load initial configuration
        self._load_configuration()
    
    def _load_configuration(self) -> None:
        """Load and apply configuration."""
        try:
            self._config = self._config_manager.load_config()
            self.fetch_timeout = self._config.global_settings.fetch_timeout_seconds
            
            if self._config.is_test_mode:
                from modules.shared.tools.glue_monitor_system.testing import mocks
                mock.init_test_mode(self._config)
                self.url = f"{self._config.server.base_url}{self._config.endpoints.weights}"
                print(f"[WeightDataFetcher] Running in TEST mode - using {self.url}")
            else:
                self.url = f"{self._config.server.base_url}{self._config.endpoints.weights}"
                print(f"[WeightDataFetcher] Running in PRODUCTION mode - using {self.url}")
            
            # Initialize weights
            for cell in self._config.cells:
                self._weights[cell.id] = 0.0
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"[WeightDataFetcher] Failed to load configuration: {e}") from e
    
    def start(self) -> None:
        """Start the data fetching thread."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_thread.clear()
            self._thread = threading.Thread(target=self._fetch_loop, daemon=True)
            self._thread.start()
            log_if_enabled(LoggingLevel.INFO, "[WeightDataFetcher] Started data fetching thread")
    
    def stop(self) -> None:
        """Stop the data fetching thread."""
        self._stop_thread.set()
        if self._thread is not None:
            self._thread.join()
            log_if_enabled(LoggingLevel.INFO, "[WeightDataFetcher] Stopped data fetching thread")
    
    def get_weights(self) -> Dict[int, float]:
        """Get current weights for all cells."""
        with self._lock:
            return self._weights.copy()
    
    def get_weight(self, cell_id: int) -> Optional[float]:
        """Get weight for a specific cell."""
        with self._lock:
            return self._weights.get(cell_id)
    
    def reload_config(self) -> None:
        """Reload configuration and restart with new settings."""
        log_if_enabled(LoggingLevel.INFO, "[WeightDataFetcher] Reloading configuration...")
        
        # Stop current thread
        was_running = self._thread is not None and self._thread.is_alive()
        if was_running:
            self.stop()
        
        # Reload configuration
        try:
            self._load_configuration()
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"[WeightDataFetcher] Failed to reload configuration: {e}") from e
        
        # Restart if it was running
        if was_running:
            self.start()
    
    def _fetch_loop(self) -> None:
        """Main fetch loop running in background thread."""
        if self._config is None:
            log_if_enabled(LoggingLevel.ERROR, "[WeightDataFetcher] No configuration loaded")
            return
        
        sleep_interval = self._config.global_settings.data_fetch_interval_ms / 1000.0
        
        while not self._stop_thread.is_set():
            try:
                self._fetch_and_publish()
            except Exception as e:
                log_if_enabled(LoggingLevel.ERROR, f"[WeightDataFetcher] Error in fetch loop: {e}")
            
            time.sleep(sleep_interval)
    
    def _fetch_and_publish(self) -> None:
        """Fetch weight data and publish to message broker."""
        if not self.url:
            log_if_enabled(LoggingLevel.WARNING, "[WeightDataFetcher] No URL configured")
            return
        
        log_if_enabled(LoggingLevel.DEBUG, f"Fetching weights from {self.url}")
        
        try:
            response = requests.get(self.url, timeout=self.fetch_timeout)
            response.raise_for_status()
            weights_data = json.loads(response.text.strip())
            
            # Update weights with strict validation
            new_weights = self._parse_weights(weights_data)

            with self._lock:
                self._weights.update(new_weights)

            # Publish to message broker
            self._data_publisher.publish_weights(new_weights)

            log_if_enabled(LoggingLevel.DEBUG, f"Raw weights received: {weights_data}")
            log_if_enabled(LoggingLevel.INFO, "WEIGHT DATA UPDATED:")
            for cell_id, weight in new_weights.items():
                log_if_enabled(LoggingLevel.INFO, f"  ├─ Weight {cell_id}: {weight:.2f}g")
            log_if_enabled(LoggingLevel.DEBUG, "Published weights to message broker")

        except requests.exceptions.ConnectionError:
            weights_list = [self._weights.get(1, 0), self._weights.get(2, 0), self._weights.get(3, 0)]
            error_handling.handle_connection_error(self.url, weights_list)
            # Update weights from modified list
            with self._lock:
                self._weights.update({1: weights_list[0], 2: weights_list[1], 3: weights_list[2]})

        except requests.exceptions.Timeout:
            error_handling.handle_timeout(self.url, self.fetch_timeout)

        except requests.exceptions.HTTPError as e:
            weights_list = [self._weights.get(1, 0), self._weights.get(2, 0), self._weights.get(3, 0)]
            error_handling.handle_HTTPError(e, self.url, weights_list)
            # Update weights from modified list
            with self._lock:
                self._weights.update({1: weights_list[0], 2: weights_list[1], 3: weights_list[2]})

        except json.JSONDecodeError:
            error_handling.handle_JSONDecodeError(self.url)

        except ValueError as e:
            error_handling.handle_value_error(e)

        except Exception as e:
            error_handling.handle_generic_exception(e)

    def _parse_weights(self, weights_data: dict) -> Dict[int, float]:
        """Parse weight data with strict validation (no defaults)."""
        try:
            parsed_weights = {}

            # Validate that all expected weight fields are present
            for cell in self._config.cells:
                weight_key = f"weight{cell.id}"
                if weight_key not in weights_data:
                    raise ValueError(f"Missing required weight field: {weight_key}")

                try:
                    parsed_weights[cell.id] = float(weights_data[weight_key])
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid weight value for {weight_key}: {weights_data[weight_key]}") from e

            return parsed_weights

        except KeyError as e:
            raise ValueError(f"Missing required weight field: {e}") from e

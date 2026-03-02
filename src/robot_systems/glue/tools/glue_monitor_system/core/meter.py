import requests

from modules.SensorPublisher import Sensor
from modules.shared.tools.glue_monitor_system.services.legacy_fetcher import GlueDataFetcher
from modules.utils.custom_logging import log_if_enabled, LoggingLevel


class GlueMeter(Sensor):
    """
    Represents a glue meter used to measure the weight of glue in a container.

    Attributes:
        url (str): The URL endpoint for fetching glue weight data.
        fetchTimeout (int): The timeout duration (in seconds) for HTTP requests.

    Methods:
        __init__(url, fetchTimeout=2):
            Initializes a GlueMeter instance with the specified URL and timeout.
        setFetchTimeout(timeout):
            Sets the timeout duration for HTTP requests.
        setUrl(url):
            Sets the URL endpoint for fetching glue weight data.
        fetchData():
            Fetches the current glue weight from the URL and calculates the net weight.
        __str__():
            Returns a string representation of the GlueMeter instance.
    """

    def __init__(self, id, url, name, state, fetchTimeout=10, useLowPass=False, alpha=0.3):
        super().__init__(name, state)
        self.id = id
        self.name = f"GlueMeter_{self.id}"
        self.state = "initializing"  # Use lowercase for consistency
        self.setFetchTimeout(fetchTimeout)
        self.setUrl(url)
        self.smoothedValue = None
        self.pollTime = 0.5
        self.type = "http"
        self.useLowPass = useLowPass
        self.alpha = alpha  # Smoothing factor for low-pass filter
        self.lastValue = None  # Last smoothed value for low-pass
        self.fetcher = GlueDataFetcher()

        # Get state from fetcher's state manager
        from modules.shared.tools.glue_monitor_system.core.state_machine import CellState
        self._get_state_from_manager()

    def setFetchTimeout(self, timeout):
        """
        Sets the timeout duration for HTTP requests.

        Args:
            timeout (int): The timeout duration (in seconds).

        Raises:
            ValueError: If timeout is less than or equal to 0.
        """
        if timeout <= 0:
            raise ValueError(f"[DEBUG] [{self.name}] fetchTimeout must be greater than 0, got {timeout}")
        self.fetchTimeout = timeout

    def setUrl(self, url):
        """
        Sets the URL endpoint for fetching glue weight data.

        Args:
            url (str): The URL endpoint.
        """
        self.url = url

    def fetchData(self):
        weight = 0
        try:
            if self.id == 1:
                weight = self.fetcher.weight1

            if self.id == 2:
                weight = self.fetcher.weight2

            if self.id == 3:
                weight = self.fetcher.weight3

            # Update state from state manager
            self._get_state_from_manager()
            self.lastValue = weight
            return weight


        except requests.exceptions.Timeout:
            self.state = "disconnected"
            log_if_enabled(LoggingLevel.WARNING, f"[{self.name}] Connection timeout")
            return None

        except requests.exceptions.RequestException as e:
            self.state = "error"
            log_if_enabled(LoggingLevel.ERROR, f"[{self.name}] Request error: {e}")
            return None

    def _get_state_from_manager(self):
        """Synchronize state from the centralized state manager"""
        try:
            cell_state = self.fetcher.state_manager.get_cell_state(self.id)
            if cell_state:
                self.state = str(cell_state)
        except Exception as e:
            log_if_enabled(LoggingLevel.WARNING, f"[{self.name}] Could not sync state: {e}")

    def __str__(self):
        """
        Returns a string representation of the GlueMeter instance.

        Returns:
            str: A string representation of the GlueMeter instance.
        """
        return f"GlueMeter(url={self.url})"

    ### SENSOR INTERFACE METHODS IMPLEMENTATION

    def getState(self):
        return self.state

    def getValue(self):
        return self.lastValue

    def getName(self):
        return self.name

    def testConnection(self):
        # Not needed, as fetchData determines state
        self.fetchData()

    def reconnect(self):
        # Not needed, as fetchData attempts a fresh HTTP request each time
        pass

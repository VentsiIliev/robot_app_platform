import logging
from typing import Any, Dict, Optional

from src.engine.hardware.weight.interfaces.i_cell_calibrator import ICellCalibrator
from src.engine.hardware.weight.interfaces.i_cell_transport import ICellTransport
from src.engine.hardware.weight.config import CalibrationConfig, CellConfig
import requests as _requests

# ── Endpoint paths ────────────────────────────────────────────────────────────
_TARE          = "/tare"
_UPDATE_OFFSET = "/update-config?offset={offset}"
_UPDATE_SCALE  = "/update-config?scale={scale}"
_UPDATE_CONFIG = "/update-config?offset={offset}&scale={scale}"


class HttpCellTransport(ICellTransport, ICellCalibrator):

    def __init__(self, config: CellConfig):
        self._config    = config
        self._base_url  = config.url.rstrip("/")
        self._timeout   = config.fetch_timeout_seconds
        self._connected = False
        self._logger    = logging.getLogger(f"{self.__class__.__name__}[cell={config.id}]")

    # ── ICellTransport ────────────────────────────────────────────────

    def connect(self) -> bool:
        try:
            self._logger.info("Connecting to %s", self._base_url)
            resp = _requests.get(self._base_url, timeout=self._timeout)
            resp.raise_for_status()
            self._connected = True
            self._logger.info("Cell %s connected", self._config.id)
            return True
        except Exception:
            self._logger.exception("connect() failed for %s", self._base_url)
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def read_weight(self) -> float:
        resp = _requests.get(self._base_url, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, (int, float)):
            return float(data)
        if isinstance(data, dict):
            return float(data.get("weight", data.get("value", 0.0)))
        raise ValueError(f"Unexpected response format from {self._base_url}: {data!r}")

    # ── ICellCalibrator ───────────────────────────────────────────────

    def tare(self, cell_id: int) -> bool:
        return self._get(_TARE) is not None

    def get_config(self, cell_id: int) -> CalibrationConfig:
        # server has no get-config endpoint — return local settings calibration
        return self._config.calibration

    def update_offset(self, cell_id: int, offset: float) -> bool:
        return self._get(_UPDATE_OFFSET.format(offset=offset)) is not None

    def update_scale(self, cell_id: int, scale: float) -> bool:
        return self._get(_UPDATE_SCALE.format(scale=scale)) is not None

    def update_config(self, cell_id: int, offset: float, scale: float) -> bool:
        return self._get(_UPDATE_CONFIG.format(offset=offset, scale=scale)) is not None

    # ── Internal ──────────────────────────────────────────────────────

    def _get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        try:
            resp = _requests.get(self._base_url + endpoint, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            self._logger.exception("GET %s failed", endpoint)
            return None

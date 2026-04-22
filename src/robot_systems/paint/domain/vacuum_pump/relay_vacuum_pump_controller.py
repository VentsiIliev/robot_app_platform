from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import ModuleType
from typing import Optional

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController

_logger = logging.getLogger(__name__)


class RelayVacuumPumpController(IVacuumPumpController):
    def __init__(
        self,
        relay_client_path: str,
        *,
        host: str = "192.168.222.35",
        port: int = 5002,
        output_num: int = 0,
    ) -> None:
        self._relay_client_path = str(relay_client_path)
        self._host = str(host)
        self._port = int(port)
        self._output_num = int(output_num)
        self._module: Optional[ModuleType] = None

    def turn_on(self) -> bool:
        return self._set_state("on")

    def turn_off(self) -> bool:
        return self._set_state("off")

    def _set_state(self, state: str) -> bool:
        module = self._load_module()
        if module is None:
            return False
        try:
            control_relay = getattr(module, "control_relay")
            response = control_relay(
                self._output_num,
                state,
                host=self._host,
                port=self._port,
            )
        except Exception:
            _logger.exception(
                "Relay vacuum pump %s failed via %s",
                state.upper(),
                self._relay_client_path,
            )
            return False

        success = bool((response or {}).get("success"))
        if success:
            _logger.info(
                "Relay vacuum pump %s output=%d host=%s port=%d",
                state.upper(),
                self._output_num,
                self._host,
                self._port,
            )
        else:
            _logger.warning(
                "Relay vacuum pump %s failed output=%d host=%s port=%d response=%s",
                state.upper(),
                self._output_num,
                self._host,
                self._port,
                response,
            )
        return success

    def _load_module(self) -> Optional[ModuleType]:
        if self._module is not None:
            return self._module
        relay_path = Path(self._relay_client_path)
        if not relay_path.exists():
            _logger.warning("Relay client script not found: %s", relay_path)
            return None
        spec = importlib.util.spec_from_file_location("paint_relay_client", relay_path)
        if spec is None or spec.loader is None:
            _logger.warning("Failed to load relay client spec from %s", relay_path)
            return None
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            _logger.exception("Failed to import relay client module from %s", relay_path)
            return None
        self._module = module
        return module


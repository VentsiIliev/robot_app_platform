from __future__ import annotations

import logging
import threading
import time

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_transport import IVacuumPumpTransport
from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig
from src.engine.core.i_health_checkable import IHealthCheckable
from src.engine.hardware.xinje import XinjeMA8X8YR

_logger = logging.getLogger(__name__)


class VacuumPumpController(IVacuumPumpController, IHealthCheckable):
    """High-level vacuum-pump controller.

    Implements turn-on/turn-off commands with optional blow-off pulse.
    Writes to a single coil/register via the injected transport.
    """

    def __init__(
        self,
        transport: IVacuumPumpTransport,
        config: VacuumPumpConfig | None = None,
    ) -> None:
        """Initialize controller.

        Args:
            transport: Hardware transport for register writes.
            config: Pump configuration (register addresses, values, blow-off).
                    Defaults to VacuumPumpConfig() if not provided.
        """
        self._transport = transport
        self._config = config or VacuumPumpConfig()
        self._pump_register = XinjeMA8X8YR.resolve_output(self._config.pump_register)
        self._blow_off_register = (
            XinjeMA8X8YR.resolve_output(self._config.blow_off_register)
            if self._config.blow_off_register is not None
            else None
        )
        self._last_operation_ok = False
        self._blow_off_lock = threading.RLock()
        self._blow_off_timer: threading.Timer | None = None
        self._blow_off_generation = 0

    def turn_on(self) -> bool:
        """Turn the vacuum pump ON.

        Closes the blow-off register first if configured, then writes the
        configured on_value to the pump register.

        Returns:
            True if the write succeeded, False otherwise.
        """
        with self._blow_off_lock:
            self._cancel_pending_blow_off_locked()
            if not self._close_blow_off():
                self._last_operation_ok = False
                return False
            self._last_operation_ok = self._write_pump(self._config.on_value, "ON")
            return self._last_operation_ok

    def turn_off(self) -> bool:
        """Turn the vacuum pump OFF and optionally pulse the blow-off.

        Writes the configured off_value to the pump register, then
        pulses the blow-off register if configured.

        Returns:
            True if both the OFF write and blow-off pulse (if any) succeeded.
            False if the OFF write failed or the blow-off pulse failed.
        """
        with self._blow_off_lock:
            self._cancel_pending_blow_off_locked()
            if not self._write_pump(self._config.off_value, "OFF"):
                self._last_operation_ok = False
                return False
            self._last_operation_ok = self._pulse_blow_off()
            return self._last_operation_ok

    def turn_off_nonblocking(self) -> bool:
        """Turn off vacuum and finish the blow-off pulse in the background."""
        with self._blow_off_lock:
            self._cancel_pending_blow_off_locked()
            if not self._write_pump(self._config.off_value, "OFF"):
                self._last_operation_ok = False
                return False
            register = self._blow_off_register
            if register is None:
                self._last_operation_ok = True
                return True
            try:
                self._transport.write_register(
                    register, int(self._config.blow_off_on_value)
                )
            except Exception:
                _logger.exception(
                    "Vacuum pump blow-off pulse failed register=%d", register
                )
                self._last_operation_ok = False
                return False
            pulse_seconds = max(0.0, float(self._config.blow_off_pulse_seconds))
            if pulse_seconds == 0.0:
                return self._finish_blow_off_locked(register)
            generation = self._blow_off_generation
            timer = threading.Timer(
                pulse_seconds,
                self._finish_blow_off_async,
                args=(register, generation),
            )
            timer.daemon = True
            self._blow_off_timer = timer
            self._last_operation_ok = True
            timer.start()
            _logger.info(
                "Vacuum pump blow-off pulse continuing asynchronously "
                "register=%d duration_s=%.3f",
                register,
                pulse_seconds,
            )
            return True

    def close(self) -> None:
        """Release the underlying Modbus transport if it owns a session."""
        with self._blow_off_lock:
            had_pending_pulse = self._cancel_pending_blow_off_locked()
            if had_pending_pulse:
                self._close_blow_off()
            self._transport.disconnect()
            self._last_operation_ok = False

    def _cancel_pending_blow_off_locked(self) -> bool:
        self._blow_off_generation += 1
        timer = self._blow_off_timer
        self._blow_off_timer = None
        if timer is not None:
            timer.cancel()
        return timer is not None

    def _finish_blow_off_async(self, register: int, generation: int) -> None:
        with self._blow_off_lock:
            if generation != self._blow_off_generation:
                return
            self._blow_off_timer = None
            if self._finish_blow_off_locked(register):
                _logger.info(
                    "Vacuum pump asynchronous blow-off pulse completed register=%d",
                    register,
                )

    def _finish_blow_off_locked(self, register: int) -> bool:
        try:
            self._transport.write_register(
                register, int(self._config.blow_off_off_value)
            )
        except Exception:
            _logger.exception("Vacuum pump blow-off close failed register=%d", register)
            self._last_operation_ok = False
            return False
        self._last_operation_ok = True
        return True

    def read_state(self) -> bool:
        """Return whether the pump output register currently contains ON."""
        try:
            value = self._transport.read_register(self._pump_register)
        except Exception:
            self._last_operation_ok = False
            raise
        self._last_operation_ok = True
        return int(value) == int(self._config.on_value)

    def is_healthy(self) -> bool:
        return self._last_operation_ok

    def _write_pump(self, value: int, label: str) -> bool:
        """Write a value to the pump register.

        Args:
            value: The value to write (typically 0=OFF, 1=ON).
            label: Human-readable label for logging ("ON" or "OFF").

        Returns:
            True if the write succeeded, False if an exception occurred.
        """
        try:
            self._transport.write_register(self._pump_register, int(value))
        except Exception:
            _logger.exception(
                "Vacuum pump %s failed register=%d value=%d",
                label,
                self._pump_register,
                value,
            )
            return False
        _logger.info(
            "Vacuum pump %s register=%d value=%d",
            label,
            self._pump_register,
            value,
        )
        return True

    def _pulse_blow_off(self) -> bool:
        """Pulse the blow-off register to clear the vacuum line.

        Writes blow_off_on_value, sleeps for blow_off_pulse_seconds,
        then writes blow_off_off_value. No-op if blow_off_register is None.

        Returns:
            True if the pulse succeeded (or if blow-off is disabled).
            False if an exception occurred during the pulse.
        """
        register = self._blow_off_register
        if register is None:
            return True
        try:
            self._transport.write_register(register, int(self._config.blow_off_on_value))
            if self._config.blow_off_pulse_seconds > 0:
                time.sleep(self._config.blow_off_pulse_seconds)
            self._transport.write_register(register, int(self._config.blow_off_off_value))
        except Exception:
            _logger.exception("Vacuum pump blow-off pulse failed register=%d", register)
            return False
        return True

    def _close_blow_off(self) -> bool:
        """Force the blow-off valve closed before creating vacuum."""
        register = self._blow_off_register
        if register is None:
            return True
        try:
            self._transport.write_register(register, int(self._config.blow_off_off_value))
        except Exception:
            _logger.exception("Vacuum pump blow-off close failed register=%d", register)
            return False
        return True

"""
Motor controller mock runner — manual integration / smoke test.

Run with:
    python src/engine/hardware/motor/mock_runner.py

No serial port required. MockMotorTransport intercepts all register I/O
and prints what would be sent over the wire.  Use it to verify
MotorController logic, ramp sequences, health-check parsing, and error
filtering without any hardware attached.

Configurable sections at the bottom of this file:
  SCENARIO  — which scenario to run
  ADDRESSES — motor addresses to test
"""
from __future__ import annotations
import logging
import sys
from typing import List

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.DEBUG,
    format = "%(levelname)-8s %(name)-25s %(message)s",
    stream = sys.stdout,
)

from src.engine.hardware.motor.interfaces.i_motor_transport import IMotorTransport
from src.engine.hardware.motor.models.motor_config import MotorConfig
from src.engine.hardware.motor.motor_controller import MotorController


# ══════════════════════════════════════════════════════════════════════════════
# MockMotorTransport
# ══════════════════════════════════════════════════════════════════════════════

class MockMotorTransport(IMotorTransport):
    """
    In-memory transport.  All register writes are recorded; reads return
    values from a configurable register bank.

    Attributes set before running a scenario:
        register_bank  – dict[address → int | list[int]] returned by reads
        raise_on_write – if True, write_registers raises IOError
        raise_on_read  – if True, reads raise IOError
        call_log       – list of (method, address, value) for assertions
    """

    def __init__(self) -> None:
        self.register_bank:  dict = {}   # address → value for reads
        self.raise_on_write: bool = False
        self.raise_on_read:  bool = False
        self.call_log:       list = []
        self._connected:     bool = False

    # ── IMotorTransport ───────────────────────────────────────────────

    def write_registers(self, address: int, values: List[int]) -> None:
        self.call_log.append(("write_registers", address, values))
        print(f"  [TRANSPORT] write_registers(addr={address}, values={values})")
        if self.raise_on_write:
            raise IOError("Simulated write failure")

    def read_register(self, address: int) -> int:
        if self.raise_on_read:
            raise IOError("Simulated read failure")
        value = self.register_bank.get(address, 0)
        self.call_log.append(("read_register", address, value))
        print(f"  [TRANSPORT] read_register(addr={address}) → {value}")
        return value

    def read_registers(self, address: int, count: int) -> List[int]:
        if self.raise_on_read:
            raise IOError("Simulated read failure")
        values = []
        for i in range(count):
            v = self.register_bank.get(address + i, 0)
            values.append(v)
        self.call_log.append(("read_registers", address, values))
        print(f"  [TRANSPORT] read_registers(addr={address}, count={count}) → {values}")
        return values

    # ── Optional lifecycle ────────────────────────────────────────────

    def connect(self) -> None:
        self._connected = True
        print("  [TRANSPORT] connect()")

    def disconnect(self) -> None:
        self._connected = False
        print("  [TRANSPORT] disconnect()")

    # ── Test helpers ──────────────────────────────────────────────────

    def set_healthy(self) -> None:
        """Configure: health check returns 0 errors."""
        cfg = MotorConfig()
        self.register_bank[cfg.motor_error_count_register] = 0

    def set_errors(self, error_codes: List[int]) -> None:
        """Configure: health check returns given error codes."""
        cfg = MotorConfig()
        self.register_bank[cfg.motor_error_count_register] = len(error_codes)
        for i, code in enumerate(error_codes):
            self.register_bank[cfg.motor_error_registers_start + i] = code

    def reset(self) -> None:
        self.register_bank.clear()
        self.call_log.clear()
        self.raise_on_write = False
        self.raise_on_read  = False


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def _make_controller(transport: MockMotorTransport) -> MotorController:
    config = MotorConfig(
        ramp_step_delay_s  = 0.0,   # no real delays in mock runner
        health_check_delay_s = 0.0,
    )
    return MotorController(transport=transport, config=config)


# ══════════════════════════════════════════════════════════════════════════════
# Scenarios
# ══════════════════════════════════════════════════════════════════════════════

def scenario_turn_on_off(t: MockMotorTransport, motor_addr: int = 0) -> None:
    """Full start-ramp-run-stop sequence for one motor."""
    _section(f"SCENARIO: turn_on / turn_off  (motor {motor_addr})")
    ctrl = _make_controller(t)

    print("\n— turn_on: speed=1000  ramp_steps=4  initial_ramp_speed=200  initial_dur=0s")
    result = ctrl.turn_on(
        motor_address             = motor_addr,
        speed                     = 1000,
        ramp_steps                = 4,
        initial_ramp_speed        = 200,
        initial_ramp_speed_duration = 0.0,
    )
    print(f"  → turn_on returned: {result}")

    print("\n— set_speed to 1500")
    result = ctrl.set_speed(motor_addr, 1500)
    print(f"  → set_speed returned: {result}")

    print("\n— turn_off: reverse_speed=300  duration=0s  ramp_steps=3")
    result = ctrl.turn_off(
        motor_address    = motor_addr,
        speed_reverse    = 300,
        reverse_duration = 0.0,
        ramp_steps       = 3,
    )
    print(f"  → turn_off returned: {result}")


def scenario_persistent_connection(t: MockMotorTransport, motor_addr: int = 0) -> None:
    """Open → repeated set_speed (hot path) → close."""
    _section(f"SCENARIO: persistent connection  (motor {motor_addr})")
    ctrl = _make_controller(t)

    print("\n— open()")
    ctrl.open()

    for spd in (500, 800, 1200, 1500):
        print(f"\n— set_speed({spd})")
        ctrl.set_speed(motor_addr, spd)

    print("\n— close()")
    ctrl.close()


def scenario_health_check_healthy(t: MockMotorTransport, motor_addr: int = 0) -> None:
    """Health check when board reports 0 errors."""
    _section(f"SCENARIO: health_check — healthy  (motor {motor_addr})")
    t.set_healthy()
    ctrl = _make_controller(t)

    state = ctrl.health_check(motor_addr)
    print(f"\n  Result: {state}")
    print(f"  is_healthy={state.is_healthy}  error_codes={state.error_codes}")


def scenario_health_check_with_errors(
    t:            MockMotorTransport,
    motor_addr:   int,
    error_codes:  List[int],
) -> None:
    """Health check when board reports specific error codes."""
    _section(f"SCENARIO: health_check — errors {error_codes}  (motor {motor_addr})")
    t.set_errors(error_codes)
    ctrl = _make_controller(t)

    state = ctrl.health_check(motor_addr)
    print(f"\n  Result: {state}")
    print(f"  is_healthy={state.is_healthy}")
    print(f"  error_codes={state.error_codes}")
    if state.error_codes:
        print("  Descriptions:")
        for desc in state.describe_errors():
            print(f"    • {desc}")


def scenario_health_check_all(
    t:             MockMotorTransport,
    motor_addrs:   List[int],
    error_codes:   List[int],
) -> None:
    """Bulk health check across multiple motors."""
    _section(f"SCENARIO: health_check_all  addresses={motor_addrs}  errors={error_codes}")
    t.set_errors(error_codes)
    ctrl = _make_controller(t)

    snapshot = ctrl.health_check_all(motor_addrs)
    print(f"\n  Snapshot: success={snapshot.success}  all_healthy={snapshot.all_healthy()}")
    for addr in motor_addrs:
        m = snapshot.get_motor(addr)
        print(f"  Motor {addr}: {m}")
    if snapshot.get_all_errors_sorted():
        print(f"  All errors (sorted): {snapshot.get_all_errors_sorted()}")


def scenario_transport_failure(t: MockMotorTransport, motor_addr: int = 0) -> None:
    """Verify controller returns False / records comm error on transport failure."""
    _section(f"SCENARIO: transport failure  (motor {motor_addr})")
    ctrl = _make_controller(t)

    print("\n— turn_on with write failure")
    t.raise_on_write = True
    result = ctrl.turn_on(motor_addr, 1000, 4, 200, 0.0)
    print(f"  → turn_on returned: {result}  (expected False)")

    t.raise_on_write = False
    t.raise_on_read  = True
    print("\n— health_check with read failure")
    state = ctrl.health_check(motor_addr)
    print(f"  → is_healthy={state.is_healthy}  comm_errors={state.communication_errors}")
    t.raise_on_read = False


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    transport = MockMotorTransport()

    scenario_turn_on_off(transport, motor_addr=0)

    transport.reset()
    scenario_persistent_connection(transport, motor_addr=0)

    transport.reset()
    scenario_health_check_healthy(transport, motor_addr=0)

    transport.reset()
    scenario_health_check_with_errors(
        transport,
        motor_addr  = 0,
        error_codes = [11, 12],   # motor 1 missing, motor 1 short
    )

    transport.reset()
    scenario_health_check_with_errors(
        transport,
        motor_addr  = 2,
        error_codes = [11, 23],   # 11 belongs to motor 0, 23 belongs to motor 2
    )

    transport.reset()
    scenario_health_check_all(
        transport,
        motor_addrs = [0, 2, 4],
        error_codes = [11, 23],   # motor 0 missing + motor 2 overheat
    )

    transport.reset()
    scenario_transport_failure(transport, motor_addr=0)

    print(f"\n{'═' * 60}")
    print("  All scenarios complete.")
    print(f"{'═' * 60}\n")

"""
Generator controller mock runner — manual integration / smoke test.

Run with:
    python src/engine/hardware/generator/mock_runner.y_pixels

No serial port required. MockGeneratorTransport intercepts all register I/O
and prints what would be sent over the wire. Use it to verify
GeneratorController logic, timer behaviour, and error handling
without any hardware attached.
"""
from __future__ import annotations
import logging
import sys

logging.basicConfig(
    level  = logging.DEBUG,
    format = "%(levelname)-8s %(name)-25s %(message)s",
    stream = sys.stdout,
)

from src.engine.hardware.generator.interfaces.i_generator_transport import IGeneratorTransport
from src.engine.hardware.generator.models.generator_config import GeneratorConfig
from src.engine.hardware.generator.models.generator_state import GeneratorState
from src.engine.hardware.generator.generator_controller import GeneratorController
from src.engine.hardware.generator.timer.generator_timer import NullGeneratorTimer, GeneratorTimer


# ══════════════════════════════════════════════════════════════════════════════
# MockGeneratorTransport
# ══════════════════════════════════════════════════════════════════════════════

class MockGeneratorTransport(IGeneratorTransport):
    """
    In-memory transport. All register writes are recorded; reads return
    values from a configurable register bank.

    Attributes:
        register_bank  – dict[address → int] returned by reads
        raise_on_write – if True, write_register raises IOError
        raise_on_read  – if True, read_register raises IOError
        call_log       – list of (method, address, value) for assertions
    """

    def __init__(self) -> None:
        self.register_bank:  dict = {}
        self.raise_on_write: bool = False
        self.raise_on_read:  bool = False
        self.call_log:       list = []

    # ── IGeneratorTransport (via IRegisterTransport) ──────────────────

    def read_register(self, address: int) -> int:
        if self.raise_on_read:
            raise IOError("Simulated read failure")
        value = self.register_bank.get(address, 0)
        self.call_log.append(("read_register", address, value))
        print(f"  [TRANSPORT] read_register(addr={address}) → {value}")
        return value

    def write_register(self, address: int, value: int) -> None:
        self.call_log.append(("write_register", address, value))
        print(f"  [TRANSPORT] write_register(addr={address}, value={value})")
        if self.raise_on_write:
            raise IOError("Simulated write failure")

    # ── Helpers ───────────────────────────────────────────────────────

    def set_on(self) -> None:
        """Configure: state register reports generator ON (hardware: 0 = ON)."""
        cfg = GeneratorConfig()
        self.register_bank[cfg.state_register] = 0

    def set_off(self) -> None:
        """Configure: state register reports generator OFF (hardware: 1 = OFF)."""
        cfg = GeneratorConfig()
        self.register_bank[cfg.state_register] = 1

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


def _make_controller(
    transport: MockGeneratorTransport,
    timeout_cb=None,
    timeout_minutes: float = 0.0,
) -> GeneratorController:
    config = GeneratorConfig(timeout_minutes=timeout_minutes)
    timer  = (
        GeneratorTimer(timeout_minutes=timeout_minutes, on_timeout=timeout_cb, poll_interval_s=0.1)
        if timeout_cb is not None
        else NullGeneratorTimer()
    )
    return GeneratorController(transport=transport, config=config, timer=timer)


# ══════════════════════════════════════════════════════════════════════════════
# Scenarios
# ══════════════════════════════════════════════════════════════════════════════

def scenario_turn_on_off(t: MockGeneratorTransport) -> None:
    """Basic turn_on / get_state / turn_off sequence."""
    _section("SCENARIO: turn_on / get_state / turn_off")
    ctrl = _make_controller(t)

    print("\n— turn_on()")
    result = ctrl.turn_on()
    print(f"  → returned: {result}  (expected True)")

    t.set_on()
    print("\n— get_state() [board reports ON]")
    state = ctrl.get_state()
    print(f"  → {state}")
    print(f"  is_on={state.is_on}  is_healthy={state.is_healthy}")

    print("\n— turn_off()")
    result = ctrl.turn_off()
    print(f"  → returned: {result}  (expected True)")

    t.set_off()
    print("\n— get_state() [board reports OFF]")
    state = ctrl.get_state()
    print(f"  → {state}")
    print(f"  is_on={state.is_on}  is_healthy={state.is_healthy}")


def scenario_get_state_on_and_off(t: MockGeneratorTransport) -> None:
    """Verify state register decoding for both ON and OFF."""
    _section("SCENARIO: get_state — ON and OFF decoding")
    ctrl = _make_controller(t)

    t.set_on()
    state = ctrl.get_state()
    print(f"\n  Board ON  → is_on={state.is_on}  (expected True)")

    t.set_off()
    state = ctrl.get_state()
    print(f"  Board OFF → is_on={state.is_on}  (expected False)")


def scenario_timeout(t: MockGeneratorTransport) -> None:
    """Verify timer fires on_timeout after configured duration."""
    import time
    _section("SCENARIO: timeout (0.05 min = 3s)")

    fired = []
    ctrl  = _make_controller(t, timeout_cb=lambda: fired.append(True), timeout_minutes=0.05)

    print("\n— turn_on() — starts timer")
    ctrl.turn_on()

    print("  Waiting 4s for timeout to fire ...")
    time.sleep(4)

    print(f"  → timeout fired: {bool(fired)}  (expected True)")
    ctrl.turn_off()


def scenario_elapsed_time(t: MockGeneratorTransport) -> None:
    """Verify elapsed_seconds increments while running."""
    import time
    _section("SCENARIO: elapsed_seconds tracking")
    ctrl = _make_controller(t, timeout_cb=lambda: None, timeout_minutes=60.0)

    ctrl.turn_on()
    time.sleep(0.5)
    state = ctrl.get_state()
    print(f"\n  After 0.5s → elapsed={state.elapsed_seconds:.2f}s  (expected ~0.5)")

    ctrl.turn_off()
    state = ctrl.get_state()
    print(f"  After stop  → elapsed={state.elapsed_seconds:.2f}s  (should stop incrementing)")


def scenario_transport_failure(t: MockGeneratorTransport) -> None:
    """Verify controller returns False and records comm error on failure."""
    _section("SCENARIO: transport failure")
    ctrl = _make_controller(t)

    print("\n— turn_on with write failure")
    t.raise_on_write = True
    result = ctrl.turn_on()
    print(f"  → returned: {result}  (expected False)")
    t.raise_on_write = False

    print("\n— get_state with read failure")
    t.raise_on_read = True
    state = ctrl.get_state()
    print(f"  → is_healthy={state.is_healthy}  comm_errors={state.communication_errors}")
    t.raise_on_read = False


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    transport = MockGeneratorTransport()

    scenario_turn_on_off(transport)

    transport.reset()
    scenario_get_state_on_and_off(transport)

    transport.reset()
    scenario_timeout(transport)

    transport.reset()
    scenario_elapsed_time(transport)

    transport.reset()
    scenario_transport_failure(transport)

    print(f"\n{'═' * 60}")
    print("  All scenarios complete.")
    print(f"{'═' * 60}\n")
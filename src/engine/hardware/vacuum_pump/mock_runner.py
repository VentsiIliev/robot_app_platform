from __future__ import annotations

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_transport import IVacuumPumpTransport
from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig
from src.engine.hardware.vacuum_pump.vacuum_pump_controller import VacuumPumpController


# ── Mock transport ─────────────────────────────────────────────────────────────

class MockVacuumPumpTransport(IVacuumPumpTransport):
    def __init__(self) -> None:
        self.register_bank:  dict = {}
        self.raise_on_write: bool = False
        self.raise_on_read:  bool = False
        self.call_log:       list = []

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
        self.register_bank[address] = value


# ── Scenarios ──────────────────────────────────────────────────────────────────

def scenario_turn_on_off():
    print("\n=== scenario: turn_on / turn_off (no blow-off) ===")
    transport = MockVacuumPumpTransport()
    config    = VacuumPumpConfig(pump_register=1)
    ctrl      = VacuumPumpController(transport, config)

    assert ctrl.turn_on()  is True,  "turn_on should succeed"
    assert transport.register_bank.get(1) == 1, "pump register should be ON (1)"

    assert ctrl.turn_off() is True,  "turn_off should succeed"
    assert transport.register_bank.get(1) == 0, "pump register should be OFF (0)"
    print("PASS")


def scenario_blow_off_pulse():
    print("\n=== scenario: turn_off with blow-off pulse ===")

    transport = MockVacuumPumpTransport()
    config    = VacuumPumpConfig(
        pump_register          = 1,
        blow_off_register      = 2,
        blow_off_pulse_seconds = 0.05,
    )
    ctrl = VacuumPumpController(transport, config)

    ctrl.turn_on()
    ctrl.turn_off()

    writes = [(a, v) for (m, a, v) in transport.call_log if m == "write_register"]
    assert (1, 1) in writes, "pump ON write expected"
    assert (1, 0) in writes, "pump OFF write expected"
    assert (2, 1) in writes, "blow-off ON write expected"
    assert (2, 0) in writes, "blow-off OFF write expected"
    # order matters: pump off → blow-off on → blow-off off
    pump_off_idx    = next(i for i, (a, v) in enumerate(writes) if a == 1 and v == 0)
    blowon_idx      = next(i for i, (a, v) in enumerate(writes) if a == 2 and v == 1)
    blowoff_idx     = next(i for i, (a, v) in enumerate(writes) if a == 2 and v == 0)
    assert pump_off_idx < blowon_idx < blowoff_idx, "write order wrong"
    print("PASS")


def scenario_transport_failure():
    print("\n=== scenario: transport failure ===")
    transport = MockVacuumPumpTransport()
    transport.raise_on_write = True
    ctrl = VacuumPumpController(transport)

    assert ctrl.turn_on()  is False, "turn_on should fail gracefully"
    assert ctrl.turn_off() is False, "turn_off should fail gracefully"
    print("PASS")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")

    scenario_turn_on_off()
    scenario_blow_off_pulse()
    scenario_transport_failure()

    print("\nAll scenarios passed.")


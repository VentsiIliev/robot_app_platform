from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from src.engine.hardware.vacuum_sensor.dummy_vacuum_sensor_transport import DummyVacuumSensorTransport
from src.engine.hardware.vacuum_sensor.models.vacuum_sensor_config import VacuumSensorConfig
from src.engine.hardware.vacuum_sensor.vacuum_sensor_service import VacuumSensorService


def scenario_vacuum_present_absent():
    print("\n=== scenario: vacuum present / absent ===")

    transport = DummyVacuumSensorTransport(simulated_value=1)
    service = VacuumSensorService(
        transport=transport,
        config=VacuumSensorConfig(sensor_register=130),
    )

    assert service.is_vacuum_detected() is True, "vacuum should be detected"
    assert service.is_healthy() is True, "sensor should be healthy"

    transport.simulated_value = 0
    assert service.is_vacuum_detected() is False, "vacuum should NOT be detected"
    assert service.is_healthy() is True, "sensor should still be healthy"
    print("PASS")


def scenario_active_low_sensor():
    print("\n=== scenario: active-low sensor (detected_value=0) ===")

    transport = DummyVacuumSensorTransport(simulated_value=0)
    service = VacuumSensorService(
        transport=transport,
        config=VacuumSensorConfig(sensor_register=130, detected_value=0),
    )

    assert service.is_vacuum_detected() is True, "active-low 0 should mean vacuum present"
    transport.simulated_value = 1
    assert service.is_vacuum_detected() is False, "active-low 1 should mean no vacuum"
    print("PASS")


def scenario_sensor_failure_failsafe():
    print("\n=== scenario: sensor failure is fail-safe (no vacuum) ===")

    transport = DummyVacuumSensorTransport()
    transport.raise_on_read = True
    service = VacuumSensorService(
        transport=transport,
        config=VacuumSensorConfig(sensor_register=130, read_retries=2),
    )

    assert service.is_vacuum_detected() is False, "failed read must report no vacuum"
    assert service.is_healthy() is False, "sensor must be unhealthy after failure"
    assert len(transport.call_log) == 2, "read_retries attempts expected"
    print("PASS")


def scenario_simulate_interactive():
    print("\n=== scenario: interactive simulation ===")

    transport = DummyVacuumSensorTransport(simulated_value=1)
    service = VacuumSensorService(
        transport=transport,
        config=VacuumSensorConfig(sensor_register=130),
    )

    for value in (1, 1, 0, 1, 0, 0):
        transport.simulated_value = value
        print(f"  simulated_value={value} -> is_vacuum_detected={service.is_vacuum_detected()}")
    print("PASS")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    scenario_vacuum_present_absent()
    scenario_active_low_sensor()
    scenario_sensor_failure_failsafe()
    scenario_simulate_interactive()

    print("\nAll scenarios passed.")

"""Run and verify one real dryer NEXT_POSITION cycle without starting the robot.

This uses the same Modbus, peripheral/register, command/status, and dryer settings
as the paint platform. It requires a fresh movement cycle before accepting DONE.
Press Ctrl-C to stop waiting; EJECT is never sent by this runner.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY_ROOT))

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
from src.engine.hardware.dryer.dryer_controller import DryerController
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_modbus_registers import DryerRegisterMap
from src.engine.hardware.peripherals import PeripheralConfig


SETTINGS_ROOT = REPOSITORY_ROOT / "src/robot_systems/paint/storage/settings"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def run_next_position(
    modbus_path: Path,
    peripherals_path: Path,
    dryer_settings_path: Path,
    *,
    acknowledgement_timeout_s: float,
    poll_interval_s: float,
) -> bool:
    modbus_config = ModbusConfig.from_dict(_load_json(modbus_path))
    peripherals = PeripheralConfig.from_dict(_load_json(peripherals_path))
    dryer_config = DryerConfig.from_dict(_load_json(dryer_settings_path))
    binding = peripherals.peripherals.get("dryer")
    if binding is None:
        raise RuntimeError(f"dryer is not configured in {peripherals_path}")

    slave_name = modbus_config.find_slave_name(binding.slave_id)
    register_map = DryerRegisterMap.from_mapping({**binding.inputs, **binding.outputs})
    transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(modbus_config, slave_name)
    controller = DryerController(
        transport,
        dryer_config,
        register_map,
        commands=binding.commands,
        statuses=binding.statuses,
        next_position_timeout_s=acknowledgement_timeout_s,
        status_poll_interval_s=poll_interval_s,
    )

    try:
        initial = controller.get_state()
        print(
            "Initial status: "
            f"raw=0x{initial.raw_status:04x} healthy={initial.is_healthy} "
            f"moving={initial.next_position_moving} done={initial.next_position_done}"
        )
        if not controller.next_position():
            print("NEXT_POSITION command write failed", file=sys.stderr)
            return False
        print("NEXT_POSITION accepted; waiting for a fresh cycle and DONE (no movement timeout)")
        return controller._wait_until_next_position_done()
    finally:
        controller.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modbus-config", type=Path, default=SETTINGS_ROOT / "hardware/modbus.json")
    parser.add_argument("--peripherals-config", type=Path, default=SETTINGS_ROOT / "hardware/peripherals.json")
    parser.add_argument("--dryer-settings", type=Path, default=SETTINGS_ROOT / "dryer/settings.json")
    parser.add_argument("--ack-timeout", type=float, default=10.0)
    parser.add_argument("--poll-interval", type=float, default=0.1)
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    try:
        success = run_next_position(
            args.modbus_config,
            args.peripherals_config,
            args.dryer_settings,
            acknowledgement_timeout_s=args.ack_timeout,
            poll_interval_s=args.poll_interval,
        )
    except KeyboardInterrupt:
        print("Interrupted while waiting for dryer status", file=sys.stderr)
        return 130
    except Exception as exc:
        logging.exception("Standalone dryer NEXT_POSITION test failed")
        print(str(exc), file=sys.stderr)
        return 1
    print("NEXT_POSITION fresh cycle completed successfully" if success else "NEXT_POSITION verification failed")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

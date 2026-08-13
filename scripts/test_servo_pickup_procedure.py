#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.engine.hardware.vacuum_sensor.dummy_vacuum_sensor_transport import (  # noqa: E402
    DummyVacuumSensorTransport,
)
from src.engine.hardware.vacuum_sensor.models.vacuum_sensor_config import (  # noqa: E402
    VacuumSensorConfig,
)
from src.engine.hardware.vacuum_sensor.vacuum_sensor_service import (  # noqa: E402
    VacuumSensorService,
)
from src.engine.robot.enums.axis import Direction, RobotAxis  # noqa: E402
from src.engine.robot.procedures import (  # noqa: E402
    ServoUntilConditionConfig,
    ServoUntilConditionProcedure,
    VacuumPickupCondition,
)


class LocalFakeRobot:
    def __init__(self) -> None:
        self.servo_active = False

    def move_ptp(self, position, tool, user, vel, acc, blocking=True):
        logging.info(
            "[LOCAL_FAKE_ROBOT] move_ptp position=%s tool=%s user=%s vel=%s acc=%s blocking=%s",
            position,
            tool,
            user,
            vel,
            acc,
            blocking,
        )
        return 0

    def start_servo_jog(
        self,
        axis,
        direction,
        linear_mm_s=None,
        angular_deg_s=None,
        *,
        frame="user",
        tool=0,
        user=0,
    ):
        self.servo_active = True
        logging.info(
            "[LOCAL_FAKE_ROBOT] start_servo_jog axis=%s direction=%s linear_mm_s=%s "
            "angular_deg_s=%s frame=%s tool=%s user=%s",
            axis,
            direction,
            linear_mm_s,
            angular_deg_s,
            frame,
            tool,
            user,
        )
        return 0

    def stop_servo_jog(self):
        logging.info("[LOCAL_FAKE_ROBOT] stop_servo_jog active_before=%s", self.servo_active)
        self.servo_active = False
        return 0


def _axis(value: str) -> RobotAxis:
    return RobotAxis.get_by_string(value)


def _direction(value: str) -> Direction:
    return Direction.get_by_string(value)


def _parse_pose(value: str | None):
    if not value:
        return None
    parts = [float(part.strip()) for part in value.split(",") if part.strip()]
    if len(parts) != 6:
        raise argparse.ArgumentTypeError("approach pose must have 6 comma-separated values")
    return parts


def _build_robot(args):
    if args.backend == "fake":
        return LocalFakeRobot()

    from src.engine.robot.drivers.client_adapters.http_websocket import (  # noqa: WPS433
        HttpWebSocketRobotClient,
    )

    return HttpWebSocketRobotClient(server_url=args.server_url)


def _start_vacuum_emulator(
    transport: DummyVacuumSensorTransport,
    *,
    detect_after_s: float,
    detected_value: int,
    clear_value: int,
) -> threading.Thread | None:
    if detect_after_s < 0.0:
        logging.info("[VACUUM_EMU] disabled; procedure will run until timeout")
        return None

    def worker() -> None:
        logging.info("[VACUUM_EMU] vacuum absent; will detect after %.3fs", detect_after_s)
        transport.set_vacuum_detected(
            False,
            detected_value=detected_value,
            clear_value=clear_value,
        )
        time.sleep(detect_after_s)
        transport.set_vacuum_detected(
            True,
            detected_value=detected_value,
            clear_value=clear_value,
        )
        logging.info("[VACUUM_EMU] vacuum detected")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test ServoUntilConditionProcedure with a dummy vacuum sensor."
    )
    parser.add_argument("--backend", choices=["fake", "http"], default="fake")
    parser.add_argument("--server-url", default="http://localhost:5000")
    parser.add_argument("--axis", default="Z", type=_axis)
    parser.add_argument("--direction", default="MINUS", type=_direction)
    parser.add_argument("--linear-mm-s", type=float, default=25.0)
    parser.add_argument("--angular-deg-s", type=float, default=None)
    parser.add_argument("--tool", type=int, default=1)
    parser.add_argument("--user", type=int, default=0)
    parser.add_argument("--frame", default="user")
    parser.add_argument("--timeout-s", type=float, default=5.0)
    parser.add_argument("--poll-interval-s", type=float, default=0.02)
    parser.add_argument("--detect-after", type=float, default=1.0)
    parser.add_argument("--detected-value", type=int, default=1)
    parser.add_argument("--clear-value", type=int, default=0)
    parser.add_argument("--sensor-register", type=int, default=0)
    parser.add_argument("--approach", type=_parse_pose, default=None)
    parser.add_argument("--approach-velocity", type=float, default=10.0)
    parser.add_argument("--approach-acceleration", type=float, default=10.0)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    robot = _build_robot(args)
    transport = DummyVacuumSensorTransport(simulated_value=args.clear_value)
    sensor = VacuumSensorService(
        transport,
        VacuumSensorConfig(
            sensor_register=args.sensor_register,
            detected_value=args.detected_value,
            read_retries=1,
        ),
    )
    condition = VacuumPickupCondition(sensor)
    procedure = ServoUntilConditionProcedure(robot, condition)

    _start_vacuum_emulator(
        transport,
        detect_after_s=float(args.detect_after),
        detected_value=int(args.detected_value),
        clear_value=int(args.clear_value),
    )

    logging.info(
        "[TEST] starting procedure backend=%s axis=%s direction=%s speed=%smm/s timeout=%ss",
        args.backend,
        args.axis.name,
        args.direction.name,
        args.linear_mm_s,
        args.timeout_s,
    )
    result = procedure.run(
        approach_pose=args.approach,
        config=ServoUntilConditionConfig(
            axis=args.axis,
            direction=args.direction,
            linear_mm_s=args.linear_mm_s,
            angular_deg_s=args.angular_deg_s,
            frame=args.frame,
            tool=args.tool,
            user=args.user,
            poll_interval_s=args.poll_interval_s,
            timeout_s=args.timeout_s,
            approach_velocity=args.approach_velocity,
            approach_acceleration=args.approach_acceleration,
        ),
    )

    logging.info("[TEST] result=%s", result)
    print(result)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())

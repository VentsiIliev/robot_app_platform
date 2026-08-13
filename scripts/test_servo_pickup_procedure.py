#!/usr/bin/env python3
from __future__ import annotations

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

BACKEND = "http"  # "fake" or "http"
SERVER_URL = "http://localhost:5000"

SERVO_AXIS = RobotAxis.Z
SERVO_DIRECTION = Direction.MINUS
SERVO_LINEAR_MM_S = 100.0
SERVO_ANGULAR_DEG_S = None
SERVO_FRAME = "user"
TOOL = 1
USER = 0

TIMEOUT_S = 5.0
POLL_INTERVAL_S = 0.02
PREFLIGHT_CONDITION_READ_ATTEMPTS = 2
CONDITION_READ_FAILURE_LIMIT = 3

# Set to -1.0 to disable simulated detection and force timeout.
DETECT_AFTER_S = 3.0
VACUUM_DETECTED_VALUE = 1
VACUUM_CLEAR_VALUE = 0
VACUUM_SENSOR_REGISTER = 0

# Set to a 6-value list to test the optional approach move first.
APPROACH_POSE = None
APPROACH_VELOCITY = 10.0
APPROACH_ACCELERATION = 10.0

LOG_LEVEL = "INFO"


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


def _build_robot():
    if BACKEND == "fake":
        return LocalFakeRobot()

    from src.engine.robot.drivers.client_adapters.http_websocket import (  # noqa: WPS433
        HttpWebSocketRobotClient,
    )

    return HttpWebSocketRobotClient(server_url=SERVER_URL)


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
    logging.basicConfig(
        level=getattr(logging, str(LOG_LEVEL).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    robot = _build_robot()
    transport = DummyVacuumSensorTransport(simulated_value=VACUUM_CLEAR_VALUE)
    sensor = VacuumSensorService(
        transport,
        VacuumSensorConfig(
            sensor_register=VACUUM_SENSOR_REGISTER,
            detected_value=VACUUM_DETECTED_VALUE,
            read_retries=1,
        ),
    )
    condition = VacuumPickupCondition(sensor)
    procedure = ServoUntilConditionProcedure(robot, condition)

    _start_vacuum_emulator(
        transport,
        detect_after_s=float(DETECT_AFTER_S),
        detected_value=int(VACUUM_DETECTED_VALUE),
        clear_value=int(VACUUM_CLEAR_VALUE),
    )

    logging.info(
        "[TEST] starting procedure backend=%s axis=%s direction=%s speed=%smm/s timeout=%ss",
        BACKEND,
        SERVO_AXIS.name,
        SERVO_DIRECTION.name,
        SERVO_LINEAR_MM_S,
        TIMEOUT_S,
    )
    result = procedure.run(
        approach_pose=APPROACH_POSE,
        config=ServoUntilConditionConfig(
            axis=SERVO_AXIS,
            direction=SERVO_DIRECTION,
            linear_mm_s=SERVO_LINEAR_MM_S,
            angular_deg_s=SERVO_ANGULAR_DEG_S,
            frame=SERVO_FRAME,
            tool=TOOL,
            user=USER,
            poll_interval_s=POLL_INTERVAL_S,
            timeout_s=TIMEOUT_S,
            preflight_condition_read_attempts=PREFLIGHT_CONDITION_READ_ATTEMPTS,
            condition_read_failure_limit=CONDITION_READ_FAILURE_LIMIT,
            approach_velocity=APPROACH_VELOCITY,
            approach_acceleration=APPROACH_ACCELERATION,
        ),
    )

    logging.info("[TEST] result=%s", result)
    print(result)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())

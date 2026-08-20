"""Hardware-only smoke test for the paint pickup servo descent.

Run from the repository root only after positioning the robot above the test part:

    python src/robot_systems/paint/run_servo_pickup_test.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.bootstrap.build_engine import EngineContext
from src.bootstrap.logging_config import setup_logging
from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.enums.axis import Direction, RobotAxis
from src.engine.robot.procedures import (
    ServoUntilConditionConfig,
    ServoUntilConditionProcedure,
    VacuumPickupCondition,
)
from src.robot_systems.paint.bootstrap_provider import PaintBootstrapProvider
from src.robot_systems.paint.component_ids import ServiceID
from src.robot_systems.system_builder import SystemBuilder

_LOGGER = logging.getLogger("paint_servo_pickup_test")
_Z_LIMIT_MM = 50.0
_SERVO_SPEED_MM_S = 250.0
_TIMEOUT_S = 30.0


def _current_z(robot_service) -> float:
    pose = robot_service.get_current_position()
    if pose is None or len(pose) < 3:
        raise RuntimeError("Robot position is unavailable; refusing to continue motion")
    return float(pose[2])


def main() -> int:
    setup_logging()
    provider = PaintBootstrapProvider()
    system = None
    vacuum_pump = None
    try:
        context = EngineContext.build()
        system = (
            SystemBuilder()
            .with_robot(provider.build_robot())
            .with_messaging_service(context.messaging_service)
            .build(provider.system_class)
        )
        robot = system.get_service(CommonServiceID.ROBOT)
        vacuum_sensor = system.get_optional_service(ServiceID.VACUUM_SENSOR)
        vacuum_pump = system.get_optional_service(ServiceID.VACUUM_PUMP)
        if vacuum_sensor is None or vacuum_pump is None:
            raise RuntimeError("Paint vacuum sensor and pump must both be configured")
        if not robot.is_healthy():
            raise RuntimeError(f"Robot is not healthy (state={robot.get_connection_state()!r})")

        starting_z = _current_z(robot)
        if starting_z <= _Z_LIMIT_MM:
            raise RuntimeError(
                f"Current Z is {starting_z:.3f} mm, already at/below the {_Z_LIMIT_MM:.1f} mm guard"
            )

        robot_config = system.get_settings(CommonSettingsID.ROBOT_CONFIG)
        tool = int(getattr(robot_config, "robot_tool", 0))
        user = int(getattr(robot_config, "robot_user", 0))

        if not vacuum_pump.turn_on():
            raise RuntimeError("Vacuum pump failed to turn on; refusing to start servo motion")

        _LOGGER.warning(
            "Starting TEST descent: z=%.3f mm speed=%.3f mm/s z_limit=%.3f mm tool=%d user=%d",
            starting_z,
            _SERVO_SPEED_MM_S,
            _Z_LIMIT_MM,
            tool,
            user,
        )
        result = ServoUntilConditionProcedure(
            robot,
            VacuumPickupCondition(vacuum_sensor),
        ).run(
            config=ServoUntilConditionConfig(
                axis=RobotAxis.Z,
                direction=Direction.MINUS,
                linear_mm_s=_SERVO_SPEED_MM_S,
                frame="user",
                tool=tool,
                user=user,
                poll_interval_s=0.02,
                timeout_s=_TIMEOUT_S,
            ),
            stop_guard=lambda: _current_z(robot) <= _Z_LIMIT_MM,
        )
        final_z = _current_z(robot)
        _LOGGER.warning(
            "Test finished: message=%s detected=%s guard=%s elapsed=%.3fs final_z=%.3f mm",
            result.message,
            result.detected,
            result.guard_triggered,
            result.elapsed_s,
            final_z,
        )
        return 0 if result.success else 1
    except KeyboardInterrupt:
        _LOGGER.warning("Interrupted by operator; stopping")
        return 130
    except Exception:
        _LOGGER.exception("Pickup servo test failed")
        return 1
    finally:
        if vacuum_pump is not None:
            try:
                vacuum_pump.turn_off()
            except Exception:
                _LOGGER.exception("Vacuum pump cleanup failed")
        if system is not None:
            system.stop()


if __name__ == "__main__":
    raise SystemExit(main())

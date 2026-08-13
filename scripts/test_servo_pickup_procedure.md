# Servo Pickup Procedure Test Runner

This note documents how to use `test_servo_pickup_procedure.py` and what must be wired before using the real vacuum sensor.

## Local Dummy Test

Run without any robot server:

```bash
cd /home/ilv/Desktop/robot_app_platform
python3 scripts/test_servo_pickup_procedure.py
```

This uses:

- `LocalFakeRobot`
- `DummyVacuumSensorTransport`
- `VacuumSensorService`
- `VacuumPickupCondition`
- `ServoUntilConditionProcedure`

The runner uses the constants at the top of `scripts/test_servo_pickup_procedure.py`.
With the default `BACKEND = "fake"` and `DETECT_AFTER_S = 3.0`, the dummy sensor changes
to vacuum-detected after three seconds. The procedure should then call `stop_servo_jog()`.

## HTTP/Fake System Test

Run against the running robot HTTP bridge:

Edit the constants near the top of `scripts/test_servo_pickup_procedure.py`:

```python
BACKEND = "http"
SERVER_URL = "http://localhost:5000"
SERVO_AXIS = RobotAxis.Z
SERVO_DIRECTION = Direction.MINUS
SERVO_LINEAR_MM_S = 10.0
TOOL = 1
USER = 0
DETECT_AFTER_S = 1.0
TIMEOUT_S = 5.0
```

Then run:

```bash
cd /home/ilv/Desktop/robot_app_platform
python3 scripts/test_servo_pickup_procedure.py
```

For a timeout/no-pickup test, set:

```python
DETECT_AFTER_S = -1
TIMEOUT_S = 3.0
```

Expected timeout result:

```text
ServoUntilConditionResult(success=False, detected=False, timed_out=True, ...)
```

## Real Sensor Wiring

To use the real vacuum sensor, replace the dummy transport with the real vacuum sensor transport.

Required pieces:

- Real `IVacuumSensorTransport`
- `VacuumSensorConfig`
- `VacuumSensorService`
- `VacuumPickupCondition`
- `ServoUntilConditionProcedure`

Example shape:

```python
from src.engine.hardware.vacuum_sensor.models.vacuum_sensor_config import VacuumSensorConfig
from src.engine.hardware.vacuum_sensor.vacuum_sensor_service import VacuumSensorService
from src.engine.robot.procedures import VacuumPickupCondition

vacuum_config = VacuumSensorConfig(
    sensor_register=YOUR_REGISTER_ADDRESS,
    detected_value=1,
    read_retries=3,
)

transport = REAL_VACUUM_SENSOR_TRANSPORT(...)
vacuum_sensor = VacuumSensorService(transport, vacuum_config)
condition = VacuumPickupCondition(vacuum_sensor)
```

Then run:

```python
from src.engine.robot.enums.axis import Direction, RobotAxis
from src.engine.robot.procedures import ServoUntilConditionConfig, ServoUntilConditionProcedure

procedure = ServoUntilConditionProcedure(robot_service, condition)

result = procedure.run(
    approach_pose=approach_pose,
    config=ServoUntilConditionConfig(
        axis=RobotAxis.Z,
        direction=Direction.MINUS,
        linear_mm_s=10.0,
        frame="user",
        tool=1,
        user=0,
        timeout_s=3.0,
        poll_interval_s=0.02,
    ),
)
```

## Values To Confirm On Real Hardware

Before running the pickup procedure on real hardware, confirm:

- correct sensor register address
- whether vacuum detected is active-high (`1`) or active-low (`0`)
- Modbus/device connection settings
- `vacuum_sensor.is_vacuum_detected()` returns `False` with no part
- `vacuum_sensor.is_vacuum_detected()` returns `True` when vacuum is present

Start conservatively:

```python
linear_mm_s = 10.0
timeout_s = 3.0
poll_interval_s = 0.02
```

Increase speed only after stop latency and sensor reliability are verified.

## Paint Process Integration

The paint process keeps the current planned pickup behavior by default.

To test servo contact pickup in the calibration/paint pickup path, configure:

```python
pickup_motion.servo_contact_enabled = True
pickup_motion.servo_contact_linear_mm_s = 10.0
pickup_motion.servo_contact_timeout_s = 5.0
pickup_motion.servo_contact_poll_interval_s = 0.02
```

To test servo contact pickup in magazine pickup, configure:

```python
pickup_motion.servo_contact_magazine_enabled = True
```

Both paths require `PaintWorkpiecePathExecutor._pickup_condition` to be set to a
condition object such as `VacuumPickupCondition(vacuum_sensor_service)`. Without a
condition, servo contact pickup fails unless this fallback is explicitly enabled:

```python
pickup_motion.servo_contact_fallback_to_planned_descend = True
```

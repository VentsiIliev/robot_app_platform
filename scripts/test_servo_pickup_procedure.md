# Servo Pickup Procedure Test Runner

This note documents how to use `test_servo_pickup_procedure.py` and what must be wired before using the real vacuum sensor.

## Local Dummy Test

Run without any robot server:

```bash
cd /home/ilv/Desktop/robot_app_platform
python3 scripts/test_servo_pickup_procedure.py --backend fake --detect-after 1.0 --timeout-s 5
```

This uses:

- `LocalFakeRobot`
- `DummyVacuumSensorTransport`
- `VacuumSensorService`
- `VacuumPickupCondition`
- `ServoUntilConditionProcedure`

The dummy sensor changes to vacuum-detected after `--detect-after` seconds. The procedure should then call `stop_servo_jog()`.

## HTTP/Fake System Test

Run against the running robot HTTP bridge:

```bash
cd /home/ilv/Desktop/robot_app_platform
python3 scripts/test_servo_pickup_procedure.py \
  --backend http \
  --server-url http://localhost:5000 \
  --axis Z \
  --direction MINUS \
  --linear-mm-s 25 \
  --tool 1 \
  --user 0 \
  --detect-after 1.0 \
  --timeout-s 5
```

Timeout/no-pickup test:

```bash
python3 scripts/test_servo_pickup_procedure.py --backend http --detect-after -1 --timeout-s 3
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

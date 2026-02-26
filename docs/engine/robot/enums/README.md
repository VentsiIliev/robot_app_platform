# `src/engine/robot/enums/` — Robot Enumerations

This package defines the core enumerations and coordinate-mapping types used throughout the robot control stack.

---

## Classes

### `RobotAxis`

**File:** `axis.py`

Cartesian and rotational axes of the robot TCP (tool center point). Used by `IMotionService.start_jog()`.

```python
class RobotAxis(Enum):
    X  = 1
    Y  = 2
    Z  = 3
    RX = 4
    RY = 5
    RZ = 6
```

| Value | Meaning |
|-------|---------|
| `X = 1` | Linear X axis (mm) |
| `Y = 2` | Linear Y axis (mm) |
| `Z = 3` | Linear Z axis (mm) |
| `RX = 4` | Rotation around X (degrees) |
| `RY = 5` | Rotation around Y (degrees) |
| `RZ = 6` | Rotation around Z (degrees) |

**Helper method:**
```python
RobotAxis.get_by_string("x")   # → RobotAxis.X
RobotAxis.get_by_string("RZ")  # → RobotAxis.RZ
```
Raises `ValueError` for unknown axis strings.

---

### `Direction`

**File:** `axis.py`

Movement direction along a `RobotAxis`. Used by `start_jog()`.

```python
class Direction(Enum):
    MINUS = -1
    PLUS  =  1
```

**Helper method:**
```python
Direction.get_by_string("plus")   # → Direction.PLUS
Direction.get_by_string("MINUS")  # → Direction.MINUS
```

The integer values (`-1` / `+1`) are passed directly to the SDK's `StartJOG` call as the `dir` parameter.

---

### `ImageAxis`

**File:** `axis.py`

Image coordinate axes for vision-guided offset calculations.

```python
class ImageAxis(Enum):
    X = auto()
    Y = auto()
```

---

### `AxisMapping`

**File:** `axis.py`

Maps a single image axis to a robot motion direction.

```python
@dataclass
class AxisMapping:
    image_axis: ImageAxis
    direction:  Direction

    def apply(self, dx_img: float, dy_img: float) -> float:
        """Extract the relevant image offset and apply direction sign."""
        ...
```

---

### `ImageToRobotMapping`

**File:** `axis.py`

Full 2D mapping from camera pixel offsets (mm) to robot Cartesian offsets (mm). Used to convert vision correction vectors into robot motion commands.

```python
@dataclass
class ImageToRobotMapping:
    robot_x: AxisMapping
    robot_y: AxisMapping

    def map(self, camera_x: float, camera_y: float) -> Tuple[float, float]:
        """
        Map image offsets to robot coordinate offsets.

        Args:
            camera_x: Offset along image X axis relative to center (mm).
            camera_y: Offset along image Y axis relative to center (mm).

        Returns:
            (robot_x_offset, robot_y_offset) in mm
        """
        ...
```

---

## Usage Example

```python
from src.engine.robot.enums.axis import RobotAxis, Direction, ImageToRobotMapping, AxisMapping, ImageAxis

# Jogging
robot_service.start_jog(
    axis=RobotAxis.Z,
    direction=Direction.MINUS,
    step=5.0,
)

# Parsing from user input
axis = RobotAxis.get_by_string("z")        # → RobotAxis.Z
direction = Direction.get_by_string("plus") # → Direction.PLUS

# Vision-to-robot coordinate mapping
mapping = ImageToRobotMapping(
    robot_x=AxisMapping(image_axis=ImageAxis.X, direction=Direction.PLUS),
    robot_y=AxisMapping(image_axis=ImageAxis.Y, direction=Direction.MINUS),
)
robot_dx, robot_dy = mapping.map(camera_x=3.5, camera_y=-2.0)
```

---

## Design Notes

- **`RobotAxis` integer values match the FairinoRobot SDK**: The SDK's `StartJOG` call accepts axis numbers 1–6. `RobotAxis` values map directly, so `axis.value` is passed without conversion.
- **`Direction` integer values are applied as multipliers**: `PLUS = 1` and `MINUS = -1` are used both as SDK `dir` arguments and as multipliers in `AxisMapping.apply()`.
- **`ImageToRobotMapping` is a pure data-transform type**: It has no dependencies on the robot service or settings. Camera-space offsets are measured in mm (after pixel-to-mm calibration) and the output is also in mm.

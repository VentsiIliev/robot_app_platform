# `src/robot_systems/glue/targeting/` — Vision Targeting

This package is the single transformation hub for the glue robot system. It replaces the scattered `TargetPointTransformer` usages that previously existed in multiple callers.

---

## Purpose

Any code that needs to convert an image pixel coordinate into a robot XY position — for a specific physical end-effector point — should go through this package. All callers share the same math, the same named points, and the same correction model.

---

## Classes

### `EndEffectorPoint`

**File:** `end_effector_point.py`

```python
@dataclass(frozen=True)
class EndEffectorPoint:
    name: str
    offset_x: float = 0.0  # local wrist-frame offset from camera center (mm)
    offset_y: float = 0.0
```

Represents a named physical point on the robot end-effector. The offset is the measured delta from the camera center to that point, expressed in the local robot wrist frame.

The camera center has `(0.0, 0.0)` offsets by definition — it is the reference from which all other points are measured.

---

### `PointRegistry`

**File:** `point_registry.py`

```python
class PointRegistry:
    def __init__(self, robot_config=None) -> None: ...

    def camera(self) -> EndEffectorPoint: ...
    def tool(self) -> EndEffectorPoint: ...
    def gripper(self) -> EndEffectorPoint: ...
    def by_name(self, name: str) -> EndEffectorPoint: ...
    def names(self) -> list[str]: ...
```

Builds the three canonical end-effector points from any config object that carries `camera_center_x/y`, `tool_point_x/y`, `gripper_point_x/y` attributes. Works with both `RobotSettings` and `PickAndPlaceConfig`.

Offsets are computed once at construction:

```
tool_offset    = tool_point    − camera_center
gripper_offset = gripper_point − camera_center
```

`by_name()` accepts the legacy string `"camera_center"` as an alias for `"camera"` so older config files and UI code continue to work without changes.

---

### `VisionTargetResolver`

**File:** `vision_target_resolver.py`

The single transformation hub for all pixel → robot XY conversions.

```python
class VisionTargetResolver:
    def __init__(
        self,
        base_transformer: ICoordinateTransformer,
        registry: PointRegistry,
        camera_to_tcp_x_offset: float = 0.0,
        camera_to_tcp_y_offset: float = 0.0,
        frames: Optional[Dict[str, TargetFrame]] = None,
    ) -> None: ...

    def resolve(
        self,
        target: PixelTarget,
        point: EndEffectorPoint,
        *,
        frame: str = TargetFrame.CALIBRATION,
        mapper: Optional[PlanePoseMapper] = None,
    ) -> TargetTransformResult: ...

    def resolve_named(
        self,
        target: PixelTarget,
        name: str,
        *,
        frame: str = TargetFrame.CALIBRATION,
        mapper: Optional[PlanePoseMapper] = None,
    ) -> TargetTransformResult: ...

    @property
    def registry(self) -> PointRegistry: ...
```

---

## Named Frames and Dynamic Mappers

Register named coordinate planes at construction via the `frames=` dict. Each `TargetFrame` bundles a `PlanePoseMapper` and an optional `IHeightCorrectionService`:

```python
resolver = VisionTargetResolver(
    base_transformer=transformer,
    registry=registry,
    camera_to_tcp_x_offset=tcp_x,
    camera_to_tcp_y_offset=tcp_y,
    frames={
        TargetFrame.CALIBRATION: TargetFrame(
            TargetFrame.CALIBRATION,
            height_correction=depth_map_service,
        ),
        TargetFrame.PICKUP: TargetFrame(
            TargetFrame.PICKUP,
            mapper=pickup_mapper,
        ),
    },
)
```

Select a frame per call:

```python
result = resolver.resolve(target, point, frame=TargetFrame.PICKUP)
```

For dynamic one-off mappers (e.g. per-capture-pose remapping), pass `mapper=` directly — it takes precedence over the frame's mapper:

```python
capture_mapper = PlanePoseMapper.from_positions(calibration_pos, capture_pose)
result = resolver.resolve(target, point, mapper=capture_mapper)
```

---

## Transformation Pipeline

Each `resolve()` call runs four steps in order:

```
pixel (px, py)
  │
  1. HomographyTransformer.transform()
  │   → calibration_xy  (calibration-plane robot XY)
  │
  2. PlanePoseMapper.map_point()   [optional; identity if no mapper]
  │   → plane_xy        (target pose frame XY)
  │
  3. Camera-to-TCP delta correction  [if current_rz is provided]
  │   delta(rz) = R(rz) · tcp_offset − R(ref_rz) · tcp_offset
  │   camera_xy = plane_xy − delta
  │
  4. End-effector offset rotation + addition  [if point has non-zero offset]
  │   rotated = R(rz) · [offset_x, offset_y]
  │   final_xy = camera_xy + rotated
  │
  └─ TargetTransformResult.final_xy
```

Steps 3 and 4 both require `current_rz`. Step 3 is skipped if `current_rz` is `None` (camera-center targeting without orientation correction). Step 4 raises `RuntimeError` if `current_rz` is `None` and the point has a non-zero offset.

---

## `TargetTransformResult`

```python
@dataclass(frozen=True)
class TargetTransformResult:
    calibration_xy: Tuple[float, float]       # after homography
    plane_xy: Tuple[float, float]             # after plane mapping
    final_xy: Tuple[float, float]             # the actual robot target
    pickup_plane_reference_delta_xy: ...      # TCP-delta correction applied
    target_delta_xy: ...                      # end-effector offset applied
    current_rz: Optional[float]
    reference_rz: Optional[float]
```

All intermediate results are preserved for logging and debugging.

---

## Callers

| Caller | How it uses the resolver |
|--------|--------------------------|
| `PickTargetApplicationService` | `resolver.resolve_named(PixelTarget(px, py, rz=rz, rx=rx, ry=ry), target, frame=...)` — uses named frames (`CALIBRATION`, `PICKUP`) with height correction |
| `PickAndPlaceWorkflow` | Stores `VisionTargetResolver` as `_resolver`; `transform_handler.py` calls `resolver.resolve_named(PixelTarget(...), target, mapper=capture_mapper)` for dynamic capture-pose remapping |
| `GlueJobBuilderService` | `resolver.resolve(PixelTarget(px, py, rz=rz, rx=180, ry=0), registry.tool())` — resolves to tool point with height correction delta |
| `WorkpieceEditorService` | `resolver.resolve(PixelTarget(px, py, rz=rz, rx=180, ry=0), registry.tool())` — same pipeline as `GlueJobBuilderService` for the execute-workpiece path |
| `application_wiring.py` | `_build_glue_vision_resolver()` builds one `PointRegistry` + `VisionTargetResolver` and shares it across applications |

---

## Construction in `application_wiring.py`

```python
base_transformer, resolver = _build_glue_vision_resolver(robot_system)
```

The helper returns `(None, None)` when vision is unavailable. All callers guard on `None` independently.

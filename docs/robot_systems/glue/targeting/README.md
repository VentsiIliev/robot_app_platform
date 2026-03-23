# Glue Usage of `src/engine/robot/targeting/`

The targeting implementation now lives in `src/engine/robot/targeting/`. This document explains how the glue robot system uses that engine-level package.

Simple mental model:
- you have a point in the camera image
- you know the Z and orientation you want
- you know which physical point should land on that target: `camera`, `tool`, or `gripper`
- `VisionTargetResolver` handles the geometry and returns the final robot pose

All glue applications use the same math here so targeting behaves the same everywhere.
Glue now also uses one shared `VisionTargetResolver` instance per robot-system runtime. It is built through `robot_system.get_shared_vision_resolver()`, cached on the robot system, and injected into applications and processes that need targeting.

---

## Main Types

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
    def __init__(
        self,
        points: Iterable[EndEffectorPoint],
        aliases: Mapping[str, str] | None = None,
    ) -> None: ...
    def by_name(self, name: str) -> EndEffectorPoint: ...
    def names(self) -> list[str]: ...
```

The engine registry is now generic. It stores whatever named points a robot system defines.

In the glue system, the canonical points and aliases are defined in:
- `src/robot_systems/glue/targeting/targeting_constants.py`
- `src/robot_systems/glue/targeting/registry.py`

Glue builds the registry from `GlueTargetingSettings`, stored separately from generic robot config.

`targeting/definitions.json` now stores:
- `POINTS`: named measured XY references in robot coordinates
- `FRAMES`: named frame definitions with optional navigation source/target groups and height-correction usage
- `ALIASES`: compatibility aliases such as `camera_center -> camera`

Offsets are computed once at construction relative to the measured `camera` point:

```
tool_offset    = tool_point    − camera_center
gripper_offset = gripper_point − camera_center
```

`by_name()` accepts the legacy string `"camera_center"` as an alias for `"camera"` in the glue system because that alias is registered by glue, not by the engine.

---

### `VisionPoseRequest`

**File:** `vision_pose_request.py`

```python
@dataclass(frozen=True)
class VisionPoseRequest:
    x_pixels: float
    y_pixels: float
    z_mm: float
    rz_degrees: float
    rx_degrees: float
    ry_degrees: float
```

This is the input request object for targeting.

It means:
- `x_pixels`, `y_pixels`: the image point to target
- `z_mm`: the base robot Z you want before height correction
- `rx_degrees`, `ry_degrees`, `rz_degrees`: the final tool orientation you want

So a request reads like:

> "Move so this image target is reached at this Z and this orientation."

The only thing not encoded in the request is which physical point should hit the target. That is provided separately as a concrete registry point:
- `registry.by_name("camera")`
- `registry.by_name("tool")`
- `registry.by_name("gripper")`

Callers are expected to pass one of these concrete registry points into the resolver.

---

### `VisionTargetResolver`

**File:** `vision_target_resolver.py`

The single transformation hub for all image-target -> robot-pose conversions.

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
        target: VisionPoseRequest,
        point: EndEffectorPoint,
        *,
        frame: str = "",
        mapper: Optional[PlanePoseMapper] = None,
    ) -> TargetTransformResult: ...

    @property
    def registry(self) -> PointRegistry: ...
```

In the glue system this resolver is not re-created per application. The shared
glue resolver is built through `BaseRobotSystem.get_shared_vision_resolver()`.

The split is now:
- generic base-system logic owns:
  - homography transformer creation
  - camera-to-TCP offset application
  - `VisionTargetResolver` assembly
- `GlueRobotSystemTargetingProvider` owns only:
  - glue point registry construction
  - glue frame-map construction
  - jog target list metadata

Consumers receive the same resolver instance and vary only the per-call request, point, and optional dynamic mapper.

---

### `JogFramePoseResolver`

**File:** `jog_frame_pose_resolver.py`

This helper applies the same physical targeting model to manual jog moves.

Simple mental model:
- the operator selects a jog frame: `camera`, `tool`, or `gripper`
- the operator presses a jog button
- the resolver computes the robot command pose needed so that the selected point moves correctly

It uses the same ingredients as vision targeting:
- `PointRegistry` for `camera/tool/gripper` offsets
- calibrated `camera_to_tcp_x_offset` / `camera_to_tcp_y_offset`
- a reference `rz` when the active plane has a known reference pose

Strings may still exist at the UI or config boundary, but they are resolved through `PointRegistry` once and the internal jog logic then uses the concrete `EndEffectorPoint`.

So manual jog moves and vision-resolved moves follow the same compensation model.

This is used by the shared glue jog wiring, not only by `PickTarget`.
`build_robot_system_jog_service(...)` now gets the generic robot/tool/user/TCP
pieces from the base robot system and only asks the targeting provider for:
- point registry
- target options
- default target

---

## Named Frames and Dynamic Mappers

Register named coordinate planes at construction via the `frames=` dict. Each `TargetFrame` bundles a `PlanePoseMapper` and an optional `IHeightCorrectionService`.

The engine no longer defines glue-specific frame names. In the glue system, frame names are defined in:
- `src/robot_systems/glue/targeting/targeting_constants.py`

Glue also provides `build_glue_target_frames(...)` which converts the stored frame definitions into runtime `TargetFrame` objects:
- a frame with empty source/target groups behaves as a named frame with no mapper
- a frame with both groups set builds a `PlanePoseMapper` from the corresponding navigation poses
- `use_height_correction=True` attaches the active height-correction service to that frame

Example:

```python
resolver = VisionTargetResolver(
    base_transformer=transformer,
    registry=registry,
    camera_to_tcp_x_offset=tcp_x,
    camera_to_tcp_y_offset=tcp_y,
    frames={
        CALIBRATION_FRAME: TargetFrame(
            CALIBRATION_FRAME,
            height_correction=depth_map_service,
        ),
        PICKUP_FRAME: TargetFrame(
            PICKUP_FRAME,
            mapper=pickup_mapper,
        ),
    },
)
```

Select a frame per call:

```python
result = resolver.resolve(target, point, frame=PICKUP_FRAME)
```

For dynamic one-off mappers (e.g. per-capture-pose remapping), pass `mapper=` directly — it takes precedence over the frame's mapper:

```python
capture_mapper = PlanePoseMapper.from_positions(calibration_pos, capture_pose)
result = resolver.resolve(target, point, mapper=capture_mapper)
```

---

## What `resolve()` Does

Each `resolve()` call takes:
- a `VisionPoseRequest`
- a physical point (`camera`, `tool`, or `gripper`)
- optionally a named frame or one-off mapper

and returns:
- intermediate XY values for debugging
- the final robot pose

The XY pipeline is:

```
pixel (x_pixels, y_pixels)
  │
  1. HomographyTransformer.transform()
  │   → calibration_xy  (calibration-plane robot XY)
  │
  2. PlanePoseMapper.map_point()   [optional; identity if no mapper]
  │   → plane_xy        (target pose frame XY)
  │
  3. Camera-to-TCP delta correction
  │   delta(rz) = R(rz) · tcp_offset − R(ref_rz) · tcp_offset
  │   camera_xy = plane_xy − delta
  │
  4. End-effector offset rotation + addition  [if point has non-zero offset]
  │   rotated = R(rz) · [offset_x, offset_y]
  │   final_xy = camera_xy + rotated
  │
  5. Frame height correction
  │   final_z = target.z_mm + z_correction(final_xy)
  │
  └─ final robot pose [x, y, z, rx, ry, rz]
```

Important detail:
- the TCP delta is applied relative to the active mapper reference pose
- if the mapper already represents a pickup plane at `rz=90`, and the request also uses `rz=90`, the delta is naturally zero
- `camera`, `tool`, and `gripper` all still go through the same TCP-delta logic; what differs is only the final point offset

So in simple terms:
- `camera` means "use the camera center as the hitting point"
- `tool` means "use the tool point as the hitting point"
- `gripper` means "use the gripper point as the hitting point"

---

## Typical Usage

```python
result = resolver.resolve(
    VisionPoseRequest(
        x_pixels=px,
        y_pixels=py,
        z_mm=base_z,
        rz_degrees=rz,
        rx_degrees=180.0,
        ry_degrees=0.0,
    ),
    resolver.registry.by_name("tool"),
)

pose = result.robot_pose()  # [x, y, z, rx, ry, rz]
```

This reads as:

> "Resolve this image point into the final robot pose for the `tool` point."

For manual jogging, the shared glue jog path uses `JogFramePoseResolver` instead of `VisionTargetResolver`, because jog commands start from the current robot pose rather than from image pixels.

---

## `TargetTransformResult`

```python
@dataclass(frozen=True)
class TargetTransformResult:
    calibration_xy: Tuple[float, float]       # after homography
    plane_xy: Tuple[float, float]             # after plane mapping
    final_xy: Tuple[float, float]             # final robot XY target
    rx: float
    ry: float
    rz: float
    z: float                                  # final robot Z after correction
    pickup_plane_reference_delta_xy: ...      # TCP-delta correction applied
    target_delta_xy: ...                      # end-effector offset applied
    reference_rz: Optional[float]

    def robot_pose(self) -> Tuple[float, float, float, float, float, float]: ...
```

Use `result.robot_pose()` when you want the final pose ready for the robot driver.

Keep the other fields when you need diagnostics, logs, or UI overlays.

---

## Callers

| Caller | How it uses the resolver |
|--------|--------------------------|
| `PickTargetApplicationService` | stores the selected registry point and uses `resolve(VisionPoseRequest(...), point, frame=...)` to preview final robot poses |
| `PickAndPlaceWorkflow` | resolves `pickup_target` through `PointRegistry` and uses `resolve(VisionPoseRequest(...), point, mapper=capture_mapper)` for dynamic capture-pose remapping |
| `GlueJobBuilderService` | uses `resolve(VisionPoseRequest(...), registry.by_name("tool"))` to build final glue waypoints |
| `WorkpieceEditorService` | uses `resolve(VisionPoseRequest(...), registry.by_name("tool"))` to execute edited contour paths through the same pipeline |
| shared glue jog wiring | uses `JogFramePoseResolver` so manual jog moves can respect TCP delta and selected `camera/tool/gripper` point semantics |
| `BaseRobotSystem` + glue targeting provider | `get_shared_vision_resolver()` builds one `PointRegistry` + `VisionTargetResolver` and shares it across applications |

---

## Construction in `application_wiring.py`

```python
base_transformer, resolver = robot_system.get_shared_vision_resolver()
```

The helper returns `(None, None)` when vision is unavailable. All callers guard on `None` independently.

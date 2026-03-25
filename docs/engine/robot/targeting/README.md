# `src/engine/robot/targeting/` — Targeting

Generic image-to-robot-pose resolution and jog-frame targeting. The package provides:

- A named-point registry for end-effector physical points
- A resolver that converts a pixel-space target into a full robot pose
- A jog resolver that keeps a selected end-effector point stable during incremental jogging
- Settings dataclasses and a robot-system adapter contract

---

## Files

| File | Purpose |
|------|---------|
| `end_effector_point.py` | `EndEffectorPoint` — named physical offset on the tool |
| `point_registry.py` | `PointRegistry` — lookup by name with alias support |
| `vision_pose_request.py` | `VisionPoseRequest` — frozen input: pixel XY + robot Z/RX/RY/RZ |
| `vision_target_resolver.py` | `VisionTargetResolver` + `TargetTransformResult` — full pixel→pose pipeline |
| `jog_frame_pose_resolver.py` | `JogFramePoseResolver` — incremental jog keeping selected point stable |
| `target_frame.py` | `TargetFrame` — named frame bundling `PlanePoseMapper` + `IHeightCorrectionService` |
| `target_frame_settings.py` | `TargetFrameSettings` — serialisable frame config |
| `remote_tcp_settings.py` | `RemoteTcpSettings` — serialisable named TCP offset |
| `targeting_settings.py` | `TargetingSettings` + `TargetingSettingsSerializer` — combined persistent config |
| `robot_system_targeting_provider.py` | `RobotSystemTargetingProvider` — abstract adapter for robot systems |

---

## `EndEffectorPoint`

```python
@dataclass(frozen=True)
class EndEffectorPoint:
    name: str
    offset_x: float = 0.0   # mm from camera center in wrist frame
    offset_y: float = 0.0   # mm from camera center in wrist frame
```

Represents a named physical point on the end-effector (e.g. a suction cup tip or a glue nozzle). `offset_x` / `offset_y` are measured from the camera optical center in the local robot wrist frame. The camera center itself has zero offsets.

---

## `PointRegistry`

```python
class PointRegistry:
    def __init__(self, points: Iterable[EndEffectorPoint], aliases: Mapping[str, str] | None = None)
    def by_name(self, name: str) -> EndEffectorPoint: ...   # raises ValueError if unknown
    def names(self) -> List[str]: ...
```

- Lookup is case-insensitive and strips whitespace.
- `aliases` maps an alternate name to a canonical registered name. Both alias and target are normalised before storage.

---

## `VisionPoseRequest`

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

Specifies a target in mixed space: image pixels for XY, robot units for Z and rotations. `VisionTargetResolver.resolve()` handles all coordinate math from this request to a final robot pose.

---

## `VisionTargetResolver`

```python
class VisionTargetResolver:
    def __init__(
        self,
        base_transformer: ICoordinateTransformer,
        registry: PointRegistry,
        camera_to_tcp_x_offset: float = 0.0,
        camera_to_tcp_y_offset: float = 0.0,
        frames: Optional[Dict[str, TargetFrame]] = None,
    )

    def resolve(
        self,
        target: VisionPoseRequest,
        point: EndEffectorPoint,
        *,
        frame: str = "",
        mapper: Optional[PlanePoseMapper] = None,
    ) -> TargetTransformResult: ...

    def get_frame(self, name: str) -> Optional[TargetFrame]: ...

    @property
    def registry(self) -> PointRegistry: ...
```

### Resolve pipeline (in order)

1. **Homography** — `base_transformer.transform(x_pixels, y_pixels)` → calibration XY in robot mm
2. **Plane mapping** — if a `PlanePoseMapper` is active (from `frame` or explicit `mapper`), maps calibration XY into the target frame's XY
3. **TCP delta** — compensates for the camera-to-TCP offset rotating with the current `rz_degrees`; applied as a correction to plane XY
4. **End-effector point offset** — rotates `point.offset_x/y` by `rz_degrees` and adds to camera XY → `final_xy`
5. **Height correction** — calls `frame.get_z_correction(final_xy)` and adds to `target.z_mm` → `z`

### `TargetTransformResult`

```python
@dataclass(frozen=True)
class TargetTransformResult:
    calibration_xy: Tuple[float, float]         # after homography
    plane_xy:       Tuple[float, float]         # after plane mapping
    final_xy:       Tuple[float, float]         # after TCP + point offsets
    rx: float
    ry: float
    rz: float
    z:  float                                   # z_mm + height correction
    pickup_plane_reference_delta_xy: Tuple[float, float]   # TCP correction applied
    target_delta_xy:                 Tuple[float, float]   # point-offset applied
    reference_rz: Optional[float]               # frame's reference rotation

    def robot_pose(self) -> Tuple[float, float, float, float, float, float]: ...
    # Returns (x, y, z, rx, ry, rz) ready for IRobotService
```

---

## `JogFramePoseResolver`

```python
class JogFramePoseResolver:
    def __init__(
        self,
        registry: PointRegistry,
        camera_to_tcp_x_offset: float = 0.0,
        camera_to_tcp_y_offset: float = 0.0,
        reference_rz_provider: Optional[Callable[[], float]] = None,
    )

    def available_frames(self) -> list[str]: ...
    def point_for_name(self, frame_name: str) -> Optional[EndEffectorPoint]: ...
    def resolve(
        self,
        current_pose: Sequence[float],
        axis: str,        # "X", "Y", "Z", "RX", "RY", "RZ"
        direction: str,   # "plus" or "minus"
        step: float,
        point: EndEffectorPoint,
    ) -> list[float] | None: ...
```

Converts an incremental jog command (axis + direction + step) into a new absolute 6D pose, keeping the selected `EndEffectorPoint` stable at the target position in robot space.

**Axis handling:**
- `X`, `Y`, `Z` — delta is computed in the **tool frame** (rotated by current RX/RY/RZ) and applied as a world-frame XY/Z increment
- `RX`, `RY`, `RZ` — direct angular increment; no position compensation

---

## `TargetFrame`

```python
class TargetFrame:
    name: str
    work_area_id: str
    mapper: Optional[PlanePoseMapper]                    # XY plane conversion
    height_correction: Optional[IHeightCorrectionService]  # Z correction

    def get_z_correction(self, x: float, y: float) -> float: ...
    # Returns 0.0 if height_correction is None or predict_z returns None
```

Named coordinate frame registered with `VisionTargetResolver`. The `mapper` handles XY; the application layer uses `height_correction` for Z.

---

## Settings Dataclasses

### `RemoteTcpSettings`

```python
@dataclass
class RemoteTcpSettings:
    name: str
    display_name: str = ""
    x_mm: float = 0.0
    y_mm: float = 0.0
```

A named TCP offset point persisted in `TargetingSettings`. Serialised via `from_dict()` / `to_dict()`.

### `TargetFrameSettings`

```python
@dataclass
class TargetFrameSettings:
    name: str
    source_navigation_group: str = ""
    target_navigation_group: str = ""
    use_height_correction: bool = False
    work_area_id: str = ""
```

Persisted frame definition. Robot systems read these to build live `TargetFrame` objects.

### `TargetingSettings`

```python
@dataclass
class TargetingSettings:
    points: list[RemoteTcpSettings]
    frames: list[TargetFrameSettings]
```

Top-level settings object. JSON keys are `"POINTS"` and `"FRAMES"` (uppercase). `ensure_defaults()` deduplicates entries by normalised name.

`TargetingSettingsSerializer` is the `ISettingsSerializer` implementation for this type (`settings_type = "targeting"`).

---

## `RobotSystemTargetingProvider`

```python
class RobotSystemTargetingProvider(ABC):
    def build_point_registry(self) -> PointRegistry: ...
    def build_frames(self) -> dict[str, TargetFrame]: ...
    def get_target_options(self) -> list[tuple[str, str]]: ...   # (value, display_label)
    def get_default_target_name(self) -> str: ...
```

Abstract adapter that robot systems implement to supply targeting runtime pieces to the platform. The `pick_target` and `robot_settings` applications call these methods; they never import robot-system-specific code directly.

---

## Design Notes

- **TCP delta is rotation-relative** — the camera-to-TCP offset is constant in wrist space but moves in world XY as the robot rotates. The resolver computes the delta between current rotation and the frame's reference rotation to compensate.
- **Arc-length rotation in jog** — `_tool_frame_delta()` builds the full ZYX rotation matrix from the current pose to project the jog step along the correct world-space direction.
- **Name normalisation** — all registry lookups normalise to lowercase + stripped whitespace. Robot systems should use lowercase names in declarations to avoid surprises.
- **Fallback for missing frames** — `VisionTargetResolver.resolve(frame="unknown")` silently ignores the unknown frame name and falls back to calibration XY with no plane mapping or height correction.

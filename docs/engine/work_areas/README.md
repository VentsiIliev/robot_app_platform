# `src/engine/work_areas/` — Work Areas

Manages named work-area polygons and the currently active area. Work areas define the regions of interest used by the vision system for detection and brightness control, and optionally for height-map collection.

---

## Files

| File | Purpose |
|------|---------|
| `work_area_settings.py` | `NormalizedPolygon`, `WorkAreaConfig`, `WorkAreaSettings`, `WorkAreaSettingsSerializer` |
| `i_work_area_service.py` | `IWorkAreaService` — 8-method interface |
| `work_area_service.py` | `WorkAreaService` — live implementation |

---

## Data Model

### `NormalizedPolygon`

```python
NormalizedPolygon = List[List[float]]  # [[x, y], ...]  values in [0.0, 1.0]
```

Polygon points in normalised image coordinates (0–1 range). Converted to pixel coordinates on demand via the image dimensions.

### `WorkAreaConfig`

```python
@dataclass
class WorkAreaConfig:
    detection_roi:      NormalizedPolygon   # primary detection region
    brightness_roi:     NormalizedPolygon   # brightness-control region
    height_mapping_roi: NormalizedPolygon   # height-map collection region
```

Three optional polygons per work area. Each defaults to an empty list (meaning "no polygon defined").

### `WorkAreaSettings`

```python
@dataclass
class WorkAreaSettings:
    areas: Dict[str, WorkAreaConfig]   # keyed by area_id string
```

Top-level settings object. Persisted via `WorkAreaSettingsSerializer` (`settings_type = "work_area_settings"`).

---

## `IWorkAreaService`

```python
class IWorkAreaService(ABC):
    def get_active_area_id(self) -> Optional[str]: ...
    def set_active_area_id(self, area_id: str | None) -> None: ...
    def get_area_config(self, area_id: str) -> WorkAreaConfig | None: ...
    def get_area_definition(self, area_id: str) -> WorkAreaDefinition | None: ...
    def save_work_area(self, area_key: str, normalized_points: NormalizedPolygon) -> tuple[bool, str]: ...
    def get_work_area(self, area_key: str) -> NormalizedPolygon | None: ...
    def get_detection_roi_pixels(self, area_id: str, width: int, height: int): ...
    def get_brightness_roi_pixels(self, area_id: str, width: int, height: int): ...
```

---

## `WorkAreaService`

```python
class WorkAreaService(IWorkAreaService):
    def __init__(
        self,
        settings_service: ISettingsService,
        definitions: Iterable[WorkAreaDefinition] = (),
        default_active_area_id: str = "",
    )
```

### Area key convention

`save_work_area()` and `get_work_area()` use a composite key that encodes both the area ID and the polygon field:

| Key pattern | Field stored |
|-------------|-------------|
| `"<area_id>"` | `detection_roi` |
| `"<area_id>__brightness"` | `brightness_roi` |
| `"<area_id>__height_mapping"` | `height_mapping_roi` |

`get_brightness_roi_pixels()` falls back to `detection_roi` if no `brightness_roi` polygon is defined.

### Pixel conversion

`get_detection_roi_pixels()` and `get_brightness_roi_pixels()` return a `numpy.float32` array of shape `(N, 2)` in pixel coordinates, or `None` if no polygon is defined.

### Active area initialisation

- If `default_active_area_id` is provided, it is used as the initial active area.
- Otherwise the first definition in `definitions` is used.
- If no definitions are provided, the active area starts as `None`.

### Validation

`set_active_area_id()` raises `KeyError` if the requested ID is not in the known definitions (when definitions are provided). Setting `None` clears the active area.

---

## Design Notes

- **Definitions vs config** — `WorkAreaDefinition` (from `shared_contracts.declarations`) is the static, class-level declaration of a work area (name, bounds, etc.). `WorkAreaConfig` is the persisted user-drawn polygon for that area. The service holds both.
- **No broker events** — work-area changes are not published to the message broker; callers poll `get_active_area_id()` or hold a reference to the service.
- **Normalised coordinates** — all stored polygons use [0, 1] range so they are resolution-independent. Convert to pixels at render time using the actual image dimensions.

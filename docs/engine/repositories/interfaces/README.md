# `src/engine/repositories/interfaces/` — Settings Interfaces

This package defines the three abstract types that form the contract between the settings system and the rest of the platform. All concrete persistence implementations must satisfy these interfaces.

---

## Class Diagram

```
ISettingsSerializer[T]            ISettingsRepository[T]
─────────────────────             ──────────────────────
+ to_dict(settings: T)            + load() → T
+ from_dict(data: Dict) → T       + save(settings: T)
+ get_default() → T               + exists() → bool
+ settings_type: str (property)   + file_path: str

            │ used by                  │ implemented by
            ▼                          ▼
  BaseJsonSettingsRepository[T]
  (json/ package)

ISettingsService
────────────────
+ get(name) → Any
+ get_repo(name) → ISettingsRepository
+ reload(name) → Any
+ save(name, settings)

    │ implemented by
    ▼
SettingsService
```

---

## API Reference

### `ISettingsSerializer[T]`

**File:** `settings_serializer.py`

Generic interface that knows how to convert a settings object `T` to/from a JSON-compatible dict, and how to create a default instance.

```python
class ISettingsSerializer(ABC, Generic[T]):
    def to_dict(self, settings: T) -> Dict[str, Any]: ...
    def from_dict(self, data: Dict[str, Any]) -> T: ...
    def get_default(self) -> T: ...
    @property
    def settings_type(self) -> str: ...  # used for logging
```

| Method/Property | Description |
|----------------|-------------|
| `to_dict(settings)` | Serialize `T` to a JSON-compatible dict |
| `from_dict(data)` | Deserialize a dict to `T`; should use `.get()` with defaults for forward compatibility |
| `get_default()` | Return a fresh `T` with sensible defaults |
| `settings_type` | Human-readable string identifier for logging (e.g., `"robot_config"`) |

**Example implementation:**
```python
class RobotSettingsSerializer(ISettingsSerializer[RobotSettings]):
    @property
    def settings_type(self) -> str:
        return "robot_config"

    def get_default(self) -> RobotSettings:
        return RobotSettings()

    def to_dict(self, settings: RobotSettings) -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> RobotSettings:
        return RobotSettings.from_dict(data)
```

---

### `ISettingsRepository[T]`

**File:** `settings_repository.py`

Generic interface for a single-type settings store backed by a file.

```python
class ISettingsRepository(ABC, Generic[T]):
    def __init__(self, file_path: Optional[str] = None): ...
    def load(self) -> T: ...
    def save(self, settings: T) -> None: ...
    def exists(self) -> bool: ...
```

| Method | Description |
|--------|-------------|
| `load()` | Read and deserialize settings from storage; returns defaults if file missing |
| `save(settings)` | Serialize and write settings to storage |
| `exists()` | Return `True` if the backing file/resource exists |

**Exception classes (same file):**

| Class | Description |
|-------|-------------|
| `SettingsRepositoryError` | Base exception for all settings persistence errors |
| `SettingsLoadError` | Raised when `load()` fails for reasons beyond JSON parse errors |
| `SettingsSaveError` | Raised when `save()` fails (e.g., no file path set, I/O error) |

---

### `ISettingsService`

**File:** `i_settings_service.py`

High-level service interface used by plugins, robot apps, and services to access settings. Hides the multi-repository structure behind a single keyed API.

```python
class ISettingsService(ABC):
    def get(self, name: str) -> Any: ...
    def get_repo(self, name: str) -> ISettingsRepository: ...
    def reload(self, name: str) -> Any: ...
    def save(self, name: str, settings: Any) -> None: ...
```

| Method | Description |
|--------|-------------|
| `get(name)` | Return cached settings object; load from disk on first call |
| `get_repo(name)` | Access the underlying repository (for advanced use) |
| `reload(name)` | Bypass cache and reload from disk |
| `save(name, settings)` | Persist to disk and update cache |

---

## Design Notes

- **Generic typing**: `ISettingsSerializer[T]` and `ISettingsRepository[T]` are generic, allowing the type checker to verify that the serializer and repository are paired correctly for the same type `T`.
- **`settings_type` for logging only**: The `settings_type` property on `ISettingsSerializer` is used in log messages to identify which settings file is being read or written. It does not affect behavior.
- **Forward-compatible deserialization**: All `from_dict` implementations should use `data.get("key", default)` rather than `data["key"]` to handle missing fields gracefully when a new field is added to the settings class.

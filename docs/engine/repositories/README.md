# `src/engine/repositories/` — Settings System

The `repositories` package provides JSON-backed persistent settings for all robot applications. Settings are loaded lazily on first access, cached in memory, and written to disk on save. The public interface is `ISettingsService` — no module outside `repositories/` should import concrete classes directly.

---

## Architecture

```
SettingsSpec (declared in BaseRobotApp)
       │
       │  consumed by
       ▼
build_from_specs(specs, settings_root, app_class)   ← settings_service_factory.py
       │
       │  creates one repo per spec:
       ▼
BaseJsonSettingsRepository(serializer, file_path)   ← json/
       │
       │  all repos collected into:
       ▼
SettingsService(repos: Dict[str, ISettingsRepository])
       │
       │  implements:
       ▼
ISettingsService   ← the only interface plugins and services see
```

---

## Settings Flow

```
AppBuilder.build(AppClass)
  └─ build_from_specs(settings_specs, settings_root, AppClass)
        │
        │  for each SettingsSpec(name, storage_key, serializer):
        │      path = base_dir / spec.storage_key
        │      repos[spec.name] = BaseJsonSettingsRepository(serializer, path)
        │
        └─ SettingsService(repos)

On first settings_service.get("robot_config"):
  └─ SettingsService.get("robot_config")
        │
        │  not in cache → reload("robot_config")
        │      └─ BaseJsonSettingsRepository.load()
        │              ├─ file exists? → json.load → serializer.from_dict → return T
        │              └─ file missing? → write defaults → return T
        │
        └─ cache["robot_config"] = T → return T

On settings_service.save("robot_config", updated):
  └─ SettingsService.save("robot_config", updated)
        ├─ BaseJsonSettingsRepository.save(updated)
        │      └─ json.dump(serializer.to_dict(updated), file)
        └─ cache["robot_config"] = updated
```

---

## API Reference

### `ISettingsService`

**File:** `interfaces/i_settings_service.py`

The only interface plugins and services should depend on.

```python
class ISettingsService(ABC):
    def get(self, name: str) -> Any: ...
    def get_repo(self, name: str) -> ISettingsRepository: ...
    def reload(self, name: str) -> Any: ...
    def save(self, name: str, settings: Any) -> None: ...
```

| Method | Description |
|--------|-------------|
| `get(name)` | Returns cached settings; loads from disk on first call |
| `get_repo(name)` | Returns the raw `ISettingsRepository` for advanced access |
| `reload(name)` | Force re-read from disk; updates cache |
| `save(name, settings)` | Serialize to disk and update cache |

Raises `KeyError` if `name` is not registered.

---

### `SettingsService`

**File:** `settings_service.py`

Concrete implementation. Holds a dict of repositories and an in-memory cache.

```python
class SettingsService(ISettingsService):
    def __init__(self, repos: Dict[str, ISettingsRepository]): ...
```

---

### `build_from_specs`

**File:** `settings_service_factory.py`

```python
def build_from_specs(
    specs: List[SettingsSpec],
    settings_root: str,
    app_class: Type,
) -> ISettingsService: ...
```

- If `settings_root` is absolute: `base_dir = settings_root / app_class.__name__.lower()`
- If relative: `base_dir = app_class_file_dir / settings_root`
- Creates one `BaseJsonSettingsRepository` per spec
- Returns `SettingsService(repos)`

---

## File Locations

Settings files are stored relative to the robot app module or at an absolute path:

```
src/robot_apps/glue/
└── storage/
    └── settings/
        ├── robot_config.json
        ├── modbus_config.json
        ├── cells.json
        └── …
```

Each `SettingsSpec.storage_key` is the filename (e.g., `"robot_config.json"`).

---

## Usage Example

```python
# Reading settings
config: RobotSettings = settings_service.get("robot_config")
print(config.robot_ip)

# Saving updated settings
config.robot_ip = "192.168.1.100"
settings_service.save("robot_config", config)

# Force reload from disk (e.g., after external edit)
fresh = settings_service.reload("robot_config")
```

---

## Design Notes

- **Lazy loading**: `get()` only reads from disk on the first call. Subsequent calls return the in-memory cache. Use `reload()` to force a re-read.
- **Write-through cache**: `save()` writes to disk and immediately updates the cache, so subsequent `get()` calls see the new value without a disk round-trip.
- **Auto-create defaults**: If the settings file does not exist, `BaseJsonSettingsRepository.load()` creates it with default values from `serializer.get_default()`. This ensures the app always starts successfully even on a fresh installation.
- **Error handling**: JSON parse errors fall back to defaults and log a warning. Other I/O errors raise `SettingsLoadError` / `SettingsSaveError`.

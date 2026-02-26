# `src/engine/repositories/json/` — JSON Settings Repository

This package provides the single concrete `ISettingsRepository` implementation used by the platform: `BaseJsonSettingsRepository`. It stores settings as pretty-printed JSON files and handles file creation, parsing, and error recovery.

---

## Class Diagram

```
ISettingsRepository[T]
        │
        └── BaseJsonSettingsRepository[T]
                  ─────────────────────────
                  _serializer: ISettingsSerializer[T]
                  file_path:   Optional[str]   (inherited)
```

---

## API Reference

### `BaseJsonSettingsRepository[T]`

**File:** `base_json_settings_repository.py`

```python
class BaseJsonSettingsRepository(ISettingsRepository[T], Generic[T]):
    def __init__(
        self,
        serializer: ISettingsSerializer[T],
        file_path: Optional[str] = None,
    ): ...

    def load(self) -> T: ...
    def save(self, settings: T) -> None: ...
    def exists(self) -> bool: ...
```

---

#### `load() → T`

```
if no file_path:
    log warning → return serializer.get_default()

if file does not exist:
    create file with defaults → return defaults

read file → json.load(fh) → serializer.from_dict(data) → return T

on JSONDecodeError / FileNotFoundError:
    log error → return serializer.get_default()   (graceful fallback)

on other exceptions:
    raise SettingsLoadError
```

**Behavior summary:**

| Condition | Result |
|-----------|--------|
| No `file_path` set | Returns defaults (logs warning) |
| File does not exist | Creates file with defaults, returns defaults |
| File exists, valid JSON | Loads and deserializes |
| File exists, invalid JSON | Returns defaults (logs error) |
| Other I/O error | Raises `SettingsLoadError` |

---

#### `save(settings: T) → None`

```
if no file_path:
    raise SettingsSaveError

serializer.to_dict(settings) → json.dump to file (indent=2)
```

- Creates parent directories with `os.makedirs(exist_ok=True)`
- Raises `SettingsSaveError` on any failure

---

#### `exists() → bool`

Returns `True` if `file_path` is set and the file exists on disk.

---

## Data Flow

```
BaseJsonSettingsRepository.load()
        │
        ├─ os.path.exists(file_path)?
        │       No → _write_file(serializer.to_dict(get_default()))
        │             └─ os.makedirs(parent_dir, exist_ok=True)
        │                json.dump(data, fh, indent=2)
        │
        ├─ open(file_path, "r") → json.load(fh) → data: dict
        │
        └─ serializer.from_dict(data) → T

BaseJsonSettingsRepository.save(settings)
        │
        ├─ serializer.to_dict(settings) → data: dict
        │
        └─ _write_file(data)
                └─ os.makedirs(parent_dir, exist_ok=True)
                   json.dump(data, fh, indent=2)
```

---

## Usage Example

```python
from src.engine.repositories.json.base_json_settings_repository import BaseJsonSettingsRepository
from src.engine.robot.configuration.robot_settings import RobotSettings, RobotSettingsSerializer

repo = BaseJsonSettingsRepository(
    serializer=RobotSettingsSerializer(),
    file_path="/path/to/storage/robot_config.json",
)

# Load (auto-creates file with defaults if absent)
config: RobotSettings = repo.load()
print(config.robot_ip)

# Modify and save
config.robot_ip = "192.168.1.50"
repo.save(config)

print("File exists:", repo.exists())
```

---

## Design Notes

- **Pretty-printed JSON**: Files are written with `indent=2` for human readability and easy manual editing.
- **Atomic file creation on first load**: When the file is missing, `load()` creates it before returning. This means the platform always produces a complete, editable settings file on first run, even with no prior configuration.
- **Graceful JSON error fallback**: If the settings file is corrupted (invalid JSON), the platform logs an error and continues with defaults rather than crashing. This is important for robustness in production environments.
- **`Generic[T]` on both bases**: Both `ISettingsRepository[T]` and `BaseJsonSettingsRepository` carry the type parameter, enabling mypy/pyright to verify type correctness when a specific serializer is paired with a repository.

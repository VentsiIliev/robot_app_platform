# `src/applications/robot_settings/service/` — Robot Settings Service

---

## `IRobotSettingsService`

**File:** `i_robot_settings_service.py`

```python
class IRobotSettingsService(ABC):
    @abstractmethod
    def load_config(self) -> RobotSettings: ...

    @abstractmethod
    def save_config(self, config: RobotSettings) -> None: ...

    @abstractmethod
    def load_calibration(self) -> RobotCalibrationSettings: ...

    @abstractmethod
    def save_calibration(self, calibration: RobotCalibrationSettings) -> None: ...
```

The application-platform boundary. `RobotSettings` and `RobotCalibrationSettings` are defined in `src/engine/robot/configuration/`.

---

## `RobotSettingsApplicationService`

**File:** `robot_settings_application_service.py`

```python
class RobotSettingsApplicationService(IRobotSettingsService):
    def __init__(self, settings_service: ISettingsService): ...
```

| Method | Settings key | Action |
|--------|-------------|--------|
| `load_config()` | `"robot_config"` | `settings_service.get("robot_config")` |
| `save_config(config)` | `"robot_config"` | `settings_service.save("robot_config", config)` |
| `load_calibration()` | `"robot_calibration"` | `settings_service.get("robot_calibration")` |
| `save_calibration(calibration)` | `"robot_calibration"` | `settings_service.save("robot_calibration", calibration)` |

The only file in this application allowed to import `ISettingsService`.

---

## Design Notes

- **No stub in this application**: `RobotSettingsApplication` is always instantiated with the real `ISettingsService` in the robot system. Unit tests use the settings service's own stub/in-memory implementation directly.
- **Two separate keys**: `robot_config` and `robot_calibration` map to separate JSON files under `storage/settings/<app_name>/`. Keeping calibration in its own file makes it easy to back up and restore independently.

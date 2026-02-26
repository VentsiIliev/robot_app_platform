# `src/robot_apps/glue/` — Glue Robot Application

`GlueRobotApp` is the concrete robot application for automated glue dispensing. It declares 5 plugins, 6 settings files, and 5 services. It is the only `BaseRobotApp` subclass currently in the platform.

---

## Class Declaration

**File:** `glue_robot_app.py`

```python
class GlueRobotApp(BaseRobotApp):
    metadata = AppMetadata(
        name="GlueApplication",
        version="1.0.0",
        description="Automated glue dispensing application",
        settings_root="storage/settings",
    )
```

---

## Settings Files

| Key | Serializer | File Path | Type |
|-----|-----------|-----------|------|
| `"robot_config"` | `RobotSettingsSerializer` | `robot/config.json` | `RobotSettings` |
| `"robot_calibration"` | `RobotCalibrationSettingsSerializer` | `robot/calibration.json` | `RobotCalibrationSettings` |
| `"glue_settings"` | `GlueSettingsSerializer` | `glue/settings.json` | `GlueSettings` |
| `"glue_cells"` | `GlueCellsConfigSerializer` | `glue/cells.json` | `GlueCellsConfig` (3 default cells) |
| `"glue_catalog"` | `GlueCatalogSerializer` | `glue/catalog.json` | `GlueCatalog` (glue type library) |
| `"modbus_config"` | `ModbusConfigSerializer` | `hardware/modbus.json` | `ModbusConfig` |

All files are stored under `storage/settings/GlueApplication/` (app name is appended by the factory). Defaults are auto-created on first run.

---

## Services

| Name | Type | Required | Builder |
|------|------|----------|---------|
| `"robot"` | `IRobotService` | Yes | Default (`_build_robot_service`) |
| `"navigation"` | `NavigationService` | Yes | Default (`_build_navigation`) |
| `"vision"` | `VisionService` | **No** | Default (stub) |
| `"tools"` | `IToolService` | **No** | Default (skipped — no tool_changer) |
| `"weight"` | `IWeightCellService` | **No** | Custom `_build_weight_cell_service` |

`_build_weight_cell_service` reads `"glue_cells"` settings and calls `build_http_weight_cell_service(cells_config, messaging)`.

---

## Shell (Folders + Plugins)

| Folder | `folder_id` | Plugins |
|--------|------------|---------|
| Production | 1 | `GlueDashboard` |
| Service | 2 | `RobotSettings`, `GlueSettings`, `ModbusSettings`, `CellSettings` |
| Administration | 3 | — |

### Plugin Factory Functions

| Plugin Name | Factory | Service(s) Used |
|------------|---------|----------------|
| `GlueDashboard` | `_build_dashboard_plugin` | `GlueDashboardService(robot, settings, weight)` |
| `RobotSettings` | `_build_robot_settings_plugin` | `RobotSettingsPluginService(settings)` |
| `GlueSettings` | `_build_glue_settings_plugin` | `GlueSettingsPluginService(settings)` |
| `ModbusSettings` | `_build_modbus_settings_plugin` | `ModbusSettingsPluginService(settings)` + `ModbusActionService()` |
| `CellSettings` | `_build_glue_cell_settings_plugin` | `GlueCellSettingsService(settings, weight)` |

All plugin factories are module-level functions in `glue_robot_app.py`. They use lazy imports to defer plugin loading until needed.

---

## Lifecycle (`on_start` / `on_stop`)

### `on_start()`

```python
def on_start(self) -> None:
    self._robot      = self.get_service("robot")
    self._navigation = self.get_service("navigation")
    self._vision     = self.get_optional_service("vision")      # None if unavailable
    self._tools      = self.get_optional_service("tools")       # None if unavailable
    # ... load all settings into instance vars ...
    self._weight: IWeightCellService | None = self.get_optional_service("weight")
    if self._weight is not None:
        self._weight.start_monitoring(
            cell_ids   = self._glue_cells.get_all_cell_ids(),
            interval_s = 0.5,
        )
    self._robot.enable_robot()
```

### `on_stop()`

```python
def on_stop(self) -> None:
    if self._weight is not None:
        self._weight.stop_monitoring()
        self._weight.disconnect_all()
    self._robot.stop_motion()
    self._robot.disable_robot()
```

---

## Settings Shim Files

`src/robot_apps/glue/settings/` contains thin re-export shims:

| File | Content |
|------|---------|
| `modbus.py` | Re-exports `ModbusConfig`, `ModbusConfigSerializer` from engine layer |
| `robot.py` | Re-exports `RobotSettings`, `RobotSettingsSerializer` etc. from engine layer |
| `robot_calibration.py` | Legacy `RobotCalibrationConfig` class (runtime config object, not a settings serializer) |
| `cells.py` | Defines `GlueCellsConfigSerializer` with glue-specific defaults (3 cells, default IPs) |
| `glue.py` | Defines `GlueSettings` dataclass + `GlueSettingsSerializer` |
| `glue_types.py` | Defines `Glue`, `GlueCatalog` dataclasses + `GlueCatalogSerializer` |

→ Subpackages: [settings/](settings/README.md) · [dashboard/](dashboard/README.md) · [glue_settings/](glue_settings/README.md)

# `src/applications/tool_settings/` — Tool Settings

Manages the tool changer configuration: the set of available tools (`ToolDefinition`) and the physical slots (`SlotConfig`) that map slot positions to installed tools. Persists via `ISettingsService`.

---

## MVC Structure

```
tool_settings/
├── service/
│   ├── i_tool_settings_service.py             ← IToolSettingsService (8 methods)
│   ├── stub_tool_settings_service.py          ← In-memory stub
│   └── tool_settings_application_service.py  ← Delegates to SettingsService
├── model/
│   └── tool_settings_model.py                 ← Thin delegation
├── view/
│   └── tool_settings_view.py                  ← Tools table + Slots table + edit forms
├── controller/
│   └── tool_settings_controller.py
└── tool_settings_factory.py
```

---

## `IToolSettingsService`

```python
class IToolSettingsService(ABC):
    # Tools
    def get_tools(self)                                   -> List[ToolDefinition]: ...
    def add_tool(self, tool_id: int, name: str)           -> Tuple[bool, str]: ...
    def update_tool(self, tool_id: int, name: str)        -> Tuple[bool, str]: ...
    def remove_tool(self, tool_id: int)                   -> Tuple[bool, str]: ...
    # Slots
    def get_slots(self)                                   -> List[SlotConfig]: ...
    def update_slot(self, slot_id: int, tool_id: int)     -> Tuple[bool, str]: ...
    def add_slot(self, slot_id: int, tool_id: int)        -> Tuple[bool, str]: ...
    def remove_slot(self, slot_id: int)                   -> Tuple[bool, str]: ...
```

`ToolDefinition` — `{tool_id: int, name: str, ...offsets}`
`SlotConfig` — `{slot_id: int, tool_id: int}` mapping a physical slot to an installed tool

---

## `ToolSettingsApplicationService`

Reads and writes the `TOOL_CHANGER_CONFIG` settings key via `ISettingsService`. All mutating operations:
1. Load current config
2. Apply the change
3. Persist via `settings_service.save(key, config)`

---

## Wiring in `GlueRobotSystem`

```python
service = ToolSettingsApplicationService(robot_system._settings_service)
return WidgetApplication(widget_factory=lambda _ms: ToolSettingsFactory().build(service))
```

`ApplicationSpec`: `folder_id=2` (Service), icon `fa5s.tools`.

The application edits `CommonSettingsID.TOOL_CHANGER_CONFIG`. The runtime
`IToolService` is built separately by `SystemBuilder` through the shared
default builder in
[default_service_builders.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/default_service_builders.py).

`ToolChangerSettings` and `ToolChangerSettingsSerializer` are now engine-level
types in
[tool_changer_settings.py](/home/ilv/Desktop/robot_app_platform/src/engine/robot/configuration/tool_changer_settings.py),
not glue-specific settings classes.

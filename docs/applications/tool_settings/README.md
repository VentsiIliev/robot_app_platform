# `src/applications/tool_settings/` — Tool Settings

Manages the tool changer configuration: the set of available tools (`ToolDefinition`) and the physical slots (`SlotConfig`) that map slot positions to installed tools. Persists via `ISettingsService`.

This is intended to be the shared tool-settings application for any robot system that adopts the common tool contract:
- `CommonSettingsID.TOOL_CHANGER_CONFIG`

In practice, robot systems should also declare:
- `CommonServiceID.TOOLS`
- `CommonSettingsID.ROBOT_CONFIG`

because the shared runtime `IToolService` is built separately through `SystemBuilder` and validates those contracts up front.

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

## Shared Wiring Pattern

```python
service = ToolSettingsApplicationService(robot_system._settings_service)
return WidgetApplication(widget_factory=lambda _ms: ToolSettingsFactory().build(service))
```

Use this app directly in any robot system that declares the common tool settings contract. `ApplicationSpec` is typically placed in the Service folder with icon `fa5s.tools`.

The application edits `CommonSettingsID.TOOL_CHANGER_CONFIG`. The runtime
`IToolService` is built separately by `SystemBuilder` through the shared
default builder in
[default_service_builders.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/default_service_builders.py).

`ToolChangerSettings` and `ToolChangerSettingsSerializer` are now engine-level
types in
[tool_changer_settings.py](/home/ilv/Desktop/robot_app_platform/src/engine/robot/configuration/tool_changer_settings.py),
not glue-specific settings classes.

The default tool catalog and default slot layout are robot-system declarations,
not engine defaults. A robot system should declare:
- `tools`
- `tool_slots`

and wire those into `ToolChangerSettingsSerializer(default_tools=..., default_slots=...)`
inside its `settings_specs`.

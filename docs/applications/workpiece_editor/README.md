# `src/applications/workpiece_editor/` — Workpiece Editor

Interactive contour-path editor for defining glue dispensing trajectories. Operators draw or import workpiece contours on a canvas (optionally overlaid on a live camera frame), fill in metadata via a dynamic form, and save the result as a JSON workpiece file.

---

## MVC Structure

```
workpiece_editor/
├── service/
│   ├── i_workpiece_editor_service.py              ← IWorkpieceEditorService (6 methods)
│   ├── stub_workpiece_editor_service.py           ← Returns empty schema + no-op saves
│   └── workpiece_editor_service.py               ← Live impl with vision + WorkpieceService
├── model/
│   └── workpiece_editor_model.py                  ← Thin delegation
├── view/
│   └── workpiece_editor_view.py                   ← Embeds editor_core widgets
├── controller/
│   └── workpiece_editor_controller.py
├── workpiece_editor_factory.py
└── editor_core/                                   ← Self-contained canvas + form subsystem
    ├── builder.py                                 ← Assembles all editor_core widgets
    ├── adapters/
    │   └── workpiece_adapter.py                   ← raw dict ↔ EditorData conversion
    ├── config/
    │   ├── segment_editor_config.py               ← Segment settings schema + provider
    │   ├── workpiece_form_schema.py               ← Form field schema
    │   └── workpiece_form_factory.py              ← Builds the Qt form from schema
    ├── handlers/
    │   ├── SaveWorkpieceHandler.py                ← Triggered on save button
    │   ├── CaptureHandler.py                      ← Triggered on capture button
    │   └── workpiece_loader.py                    ← Loads raw dict into canvas
    ├── managers/
    │   └── workpiece_manager.py                   ← Manages canvas state + history
    ├── models/
    │   ├── workpiece.py                           ← Workpiece domain model
    │   └── workpiece_field.py                     ← Single form field
    └── ui/
        ├── Drawer.py                              ← Canvas drawing widget
        └── CreateWorkpieceForm.py                 ← Metadata form widget
```

---

## `IWorkpieceEditorService`

```python
class IWorkpieceEditorService(ABC):
    def get_form_schema(self)                     -> WorkpieceFormSchema: ...
    def get_segment_config(self)                  -> SegmentEditorConfig: ...
    def get_contours(self)                        -> list: ...
    def save_workpiece(self, data: dict)          -> tuple[bool, str]: ...
    def execute_workpiece(self, data: dict)       -> tuple[bool, str]: ...
    def set_editing(self, storage_id: Optional[str]) -> None: ...
```

`set_editing(storage_id)` — call with a storage ID to update an existing workpiece on the next `save_workpiece()`; call with `None` to create a new one.

---

## `WorkpieceEditorService`

```python
WorkpieceEditorService(
    vision_service:  Optional[IVisionService],
    save_fn:         Callable[[dict], tuple[bool, str]],
    update_fn:       Callable[[str, dict], tuple[bool, str]],
    form_schema:     Callable[[], WorkpieceFormSchema],   # lazy — re-evaluated on each open
    segment_config:  SegmentEditorConfig,
    id_exists_fn:    Callable[[str], bool],
)
```

- `get_contours()` — `vision_service.get_latest_contours()` or `[]`
- `save_workpiece(data)` — calls `update_fn(storage_id, data)` if editing; otherwise `save_fn(data)`
- `set_editing(storage_id)` — stores the ID for the next save

---

## Open-from-Library Flow

The `WorkpieceEditor` factory subscribes to `WorkpieceTopics.OPEN_IN_EDITOR` at startup via a `_PendingLoader` helper:

```
WorkpieceLibrary: broker.publish(WorkpieceTopics.OPEN_IN_EDITOR, {"raw": {...}, "storage_id": "..."})
  → _PendingLoader.on_open_requested() stores payload

User navigates to WorkpieceEditor folder
  → create_widget() is called
  → _make_widget(ms) checks pending.pop()
  → WorkpieceAdapter.from_raw(raw) converts to EditorData
  → workpiece_manager.load_editor_data(editor_data) loads canvas
  → service.set_editing(storage_id) arms save as update
```

---

## Wiring in `GlueRobotSystem`

```python
service = WorkpieceEditorService(
    vision_service = robot_system.get_optional_service(ServiceID.VISION),
    save_fn        = workpiece_service.save,
    update_fn      = workpiece_service.update,
    form_schema    = lambda: build_glue_workpiece_form_schema(...),
    segment_config = SegmentEditorConfig(schema=build_glue_segment_settings_schema(...)),
    id_exists_fn   = workpiece_service.workpiece_id_exists,
)
```

`ApplicationSpec`: `folder_id=1` (Production), icon `fa5s.draw-polygon`.

---

## Design Notes

- **`editor_core` is self-contained**: it has no dependency on the service interface or the MVC wrapper. It can be embedded in other applications.
- **Lazy form schema**: `form_schema` is a callable so glue type and tool lists are re-fetched fresh each time the editor opens — picking up any changes made in ToolSettings or GlueSettings.
- **Vision optional**: contour overlay and `get_contours()` gracefully return empty lists when vision is unavailable.

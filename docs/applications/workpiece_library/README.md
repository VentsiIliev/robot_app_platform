# `src/applications/workpiece_library/` — Workpiece Library

Browse, view, and manage saved workpiece definitions. Displays the catalogue of all stored workpieces, supports metadata editing, deletion, and opening a workpiece in the editor via a broker event.

The library view uses the shared page-title palette, card and table colors, and touch-sized actions used across application screens.

---

## MVC Structure

```
workpiece_library/
├── service/
│   ├── i_workpiece_library_service.py              ← IWorkpieceLibraryService (6 methods)
│   ├── stub_workpiece_library_service.py           ← 3 hardcoded stub records
│   └── (implementation in robot_systems/glue/domain/workpieces/)
├── model/
│   └── workpiece_library_model.py                  ← Delegation + refresh after mutating ops
├── view/
│   └── workpiece_library_view.py                   ← Table + detail panel + action buttons
├── controller/
│   └── workpiece_library_controller.py
└── workpiece_library_factory.py
```

---

## `IWorkpieceLibraryService`

```python
class IWorkpieceLibraryService(ABC):
    def list_all(self)                                    -> List[WorkpieceEntry]: ...
    def delete(self, storage_id: str)                     -> tuple[bool, str]: ...
    def update_metadata(self, storage_id: str, data: dict) -> tuple[bool, str]: ...
    def get_thumbnail(self, storage_id: str)              -> Optional[bytes]: ...
    def load_raw(self, storage_id: str)                   -> Optional[dict]: ...
    def open_in_editor(self, storage_id: str)             -> None: ...
```

`open_in_editor` publishes `WorkpieceTopics.OPEN_IN_EDITOR` via the broker, which the `WorkpieceEditor` application is subscribed to.

---

## `WorkpieceLibraryModel`

Adds one key behaviour on top of simple delegation: **refreshes the list after every mutating operation**:

```python
def delete(self, storage_id: str) -> tuple[bool, str]:
    result = self._service.delete(storage_id)
    if result[0]:
        self._entries = self._service.list_all()   # ← refresh
    return result

def update_metadata(self, storage_id: str, data: dict) -> tuple[bool, str]:
    result = self._service.update_metadata(storage_id, data)
    if result[0]:
        self._entries = self._service.list_all()   # ← refresh
    return result
```

This keeps the model's cached list consistent without the controller needing to call `load()` after every write.

---

## `GlueWorkpieceLibraryService`

The live implementation lives in `src/robot_systems/glue/domain/workpieces/glue_workpiece_library_service.py`. It wraps:

- `WorkpieceService(JsonWorkpieceRepository(path))` — CRUD on JSON files in `storage/workpieces/`
- `glue_types_fn` — callable that returns current glue type names (from `GlueCatalog`)
- `tools_fn` — callable that returns current tool options (from `ToolChangerConfig`)

---

## Wiring in `GlueRobotSystem`

```python
service = GlueWorkpieceLibraryService(
    WorkpieceService(JsonWorkpieceRepository(robot_system.workpieces_storage_path())),
    glue_types_fn = lambda: catalog.get_all_names(),
    tools_fn      = lambda: _get_tools(robot_system),
)
return WidgetApplication(widget_factory=lambda _ms: WorkpieceLibraryFactory().build(service, _ms))
```

`ApplicationSpec`: `folder_id=1` (Production), icon `fa5s.book-open`.

---

## Open-in-Editor Flow

```
User clicks "Open in Editor"
  → controller._on_open_in_editor(storage_id)
  → service.open_in_editor(storage_id)
  → broker.publish(WorkpieceTopics.OPEN_IN_EDITOR, {"raw": {...}, "storage_id": "..."})

WorkpieceEditor's _PendingLoader.on_open_requested() receives the payload
  → stores raw + storage_id
  → on next create_widget() call, auto-loads the workpiece into the editor canvas
```

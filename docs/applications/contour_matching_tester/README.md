# `src/applications/contour_matching_tester/` — Contour Matching Tester

Development and diagnostic tool for testing the contour-based workpiece matching algorithm. Runs a saved workpiece's contour template against a live camera frame and reports the match result — without triggering any robot motion.

---

## MVC Structure

```
contour_matching_tester/
├── service/
│   ├── i_contour_matching_tester_service.py              ← IContourMatchingTesterService (4 methods)
│   ├── stub_contour_matching_tester_service.py           ← 3 numpy stub workpieces
│   └── contour_matching_tester_service.py                ← Live impl with vision + workpiece services
├── model/
│   └── contour_matching_tester_model.py
├── view/
│   └── contour_matching_tester_view.py
├── controller/
│   └── contour_matching_tester_controller.py
└── contour_matching_tester_factory.py
```

---

## `IContourMatchingTesterService`

```python
class IContourMatchingTesterService(ABC):
    def get_workpieces(self)                        -> List[WorkpieceEntry]: ...
    def run_matching(self, storage_id: str)         -> tuple[bool, str, Optional[dict]]: ...
    def get_latest_frame(self)                      -> Optional[np.ndarray]: ...
    def get_latest_contours(self)                   -> list: ...
```

`run_matching` returns `(success, message, result_dict)` where `result_dict` contains match score and overlay data.

---

## `ContourMatchingTesterService`

The live implementation wraps two optional dependencies:

```python
ContourMatchingTesterService(
    vision_service:    Optional[IVisionService],   # None → matching returns failure
    workpiece_service: WorkpieceService,            # reads JSON workpiece files
)
```

- `get_workpieces()` — delegates to `workpiece_service.list_all()`
- `run_matching(storage_id)` — loads workpiece contour; calls `vision_service.get_latest_contours()` to get the live camera contour; runs the matching algorithm
- `get_latest_frame()` / `get_latest_contours()` — delegate to `vision_service` if available

If `vision_service` is `None`, `run_matching` returns `(False, "Vision unavailable", None)`.

---

## Stub

`StubContourMatchingTesterService` provides 3 synthetic workpiece entries with numpy-generated contour arrays. No camera or filesystem needed.

---

## Wiring in `GlueRobotSystem`

```python
service = ContourMatchingTesterService(
    vision_service    = robot_system.get_optional_service(ServiceID.VISION),
    workpiece_service = WorkpieceService(JsonWorkpieceRepository(_WORKPIECES_STORAGE)),
)
return WidgetApplication(widget_factory=lambda ms: ContourMatchingTesterFactory().build(service, ms))
```

`ApplicationSpec`: `folder_id=2` (Service), icon `fa5s.tools`.

---

## Design Notes

- **Vision optional**: the application loads and shows workpieces even without a camera. The "Run Match" button is disabled or returns a clear error when vision is unavailable.
- **No robot interaction**: purely a vision + file I/O tool. Safe to use during maintenance without robot enabled.

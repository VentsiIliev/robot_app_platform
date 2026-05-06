# Applications — Blueprint & Layer Violation Report

Generated: 2026-05-05

---

## Table of Contents

1. [Cross-Cutting Violations](#cross-cutting-violations)
2. [Per-Application Findings](#per-application-findings)
   - [aruco_z_probe](#1-aruco_z_probe)
   - [broker_debug](#2-broker_debug)
   - [calibration](#3-calibration)
   - [calibration_settings](#4-calibration_settings)
   - [calibration_v2](#5-calibration_v2)
   - [camera_settings](#6-camera_settings)
   - [contour_matching_tester](#7-contour_matching_tester)
   - [device_control](#8-device_control)
   - [glue_cell_settings](#9-glue_cell_settings)
   - [hand_eye_calibration](#10-hand_eye_calibration)
   - [height_measuring](#11-height_measuring)
   - [intrinsic_calibration_capture](#12-intrinsic_calibration_capture)
   - [login](#13-login)
   - [modbus_settings](#14-modbus_settings)
   - [pick_and_place_visualizer](#15-pick_and_place_visualizer)
   - [pick_target](#16-pick_target)
   - [robot_settings](#17-robot_settings)
   - [tool_settings](#18-tool_settings)
   - [user_management](#19-user_management)
   - [work_area_settings](#20-work_area_settings)
   - [workpiece_editor](#21-workpiece_editor)
   - [workpiece_library](#22-workpiece_library)

---

## Cross-Cutting Violations

| Pattern | Severity | Applications Affected |
|---------|----------|----------------------|
| View imports `app_styles` instead of `pl_gui.settings.settings_view.styles` | **High** | calibration_v2, device_control, glue_cell_settings, hand_eye_calibration, intrinsic_calibration_capture, pick_and_place_visualizer, tool_settings, work_area_settings, workpiece_editor, workpiece_library |
| Broker subscribe without matching unsubscribe | **Critical** | calibration_v2, pick_target, robot_settings, workpiece_editor |
| Factory manually assigns `view._controller` (base class owns this) | **Critical** | aruco_z_probe, pick_target |
| Factory/service breaks interface segregation | **Medium** | aruco_z_probe |
| View uses `lambda` in Qt signal connections (GC risk) | **Critical** | glue_cell_settings |
| Non-standard factory (no `ApplicationFactory` base class) | **Medium** | calibration, calibration_v2, pick_and_place_visualizer |
| Controller imports concrete service instead of interface | **Medium** | contour_matching_tester, hand_eye_calibration |
| Model/Controller calls platform service directly (bypasses app interface) | **High** | calibration (model), calibration_v2 (controller) |
| View connects Qt signals in `__init__` instead of `load()` | **Medium** | device_control, intrinsic_calibration_capture |
| Missing stub service file | **Medium** | robot_settings |
| Model or View inherits wrong base class | **Medium** | login |
| Coupled to specific robot system (paint) | **High** | tool_settings, user_management |

---

## Per-Application Findings

### 1. `aruco_z_probe`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `aruco_z_probe_factory.py` | ~34 | `view._controller = controller` assigned manually in `build()` | Factory must NOT assign `view._controller` — base class `ApplicationFactory.build()` owns this |
| 2 | `aruco_z_probe_factory.py` | ~34 | `service._controller = controller` — assigns controller onto service | Breaks Interface Segregation; service interface should not expose controller |

---

### 2. `broker_debug`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `broker_debug_application.py` | — | No factory, model, or controller defined; empty stub `BrokerDebugApplication` | Blueprint requires full MVC stack + factory |

---

### 3. `calibration`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `camera_calibration_application.py` | — | Nested `factory` function instead of `ApplicationFactory` subclass | Blueprint step 9: factory must inherit `ApplicationFactory` |
| 2 | `camera_calibration_model.py` | — | Model directly calls `calibration_manager.estimate_intrinsics()` (platform service) | Model must delegate I/O via `IMyService`, never call platform services directly |

---

### 4. `calibration_settings`

**No violations found.**

---

### 5. `calibration_v2`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `calibration_v2_factory.py` | — | Manual `Application` namedtuple instead of `ApplicationFactory` subclass | Blueprint step 9: factory must inherit `ApplicationFactory` |
| 2 | `calibration_v2_controller.py` | `load()` | Subscribes `VisionTopics.CALIBRATION_DATA` but no `unsubscribe` in `stop()` | Every `subscribe` in `load()` must have matching `unsubscribe` in `stop()` |
| 3 | `calibration_v2_controller.py` | — | Calls `self._settings_service.get_all()` directly | Controller must NOT import platform services; go through `ICalibrationService` |
| 4 | `calibration_v2_view.py` | — | Imports `app_styles` instead of `pl_gui.settings.settings_view.styles` | View styling rule: always use shared style system |

---

### 6. `camera_settings`

**No violations found.**

---

### 7. `contour_matching_tester`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `stub_contour_matching_service.py` | `_resolve()` | References undefined `self._current_point_id`, `self._current_pose`, `self._points` — stub is broken | Liskov Substitution: stub must honour every contract of the interface |
| 2 | `contour_matching_controller.py` | imports | Imports `ContourMatchingService` (concrete class) instead of `IContourMatchingService` (interface) | Dependency Inversion: depend on abstractions, not concrete classes |

---

### 8. `device_control`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `device_control_view.py` | `__init__` | `self._power_btn.clicked.connect(self._on_power_clicked)` in `__init__` | Qt signal connections should be in `load()`/initialization, not `__init__` |
| 2 | `device_control_view.py` | imports | Imports `app_styles` instead of `pl_gui.settings.settings_view.styles` | View styling rule: always use shared style system |

---

### 9. `glue_cell_settings`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `glue_cell_settings_view.py` | signal connections | Uses `lambda: self.save_requested.emit(...)` in signal connections | Signal forwarding rule: named methods only; lambdas are GC'd and silently die |
| 2 | `glue_cell_settings_view.py` | imports | Imports `app_styles` instead of `pl_gui.settings.settings_view.styles` | View styling rule: always use shared style system |

---

### 10. `hand_eye_calibration`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `stub_hand_eye_calibration_service.py` | — | Missing `record_pose()` method required by interface | Liskov Substitution: stub must implement every interface method |
| 2 | `hand_eye_calibration_controller.py` | imports | Imports `HandEyeCalibrationService` (concrete class) instead of interface | Dependency Inversion: depend on abstractions |
| 3 | `hand_eye_calibration_view.py` | imports | Imports `app_styles` instead of `pl_gui.settings.settings_view.styles` | View styling rule: always use shared style system |

---

### 11. `height_measuring`

**No violations found.**

---

### 12. `intrinsic_calibration_capture`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `intrinsic_calibration_capture_view.py` | imports | Imports `app_styles` instead of `pl_gui.settings.settings_view.styles` | View styling rule: always use shared style system |
| 2 | `intrinsic_calibration_capture_view.py` | `__init__` | `self._capture_btn.clicked.connect(...)` in `__init__` | Qt signal connections should not be in `__init__` |

---

### 13. `login`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `login_view.py` | class def | `LoginView` inherits `QWidget` instead of `IApplicationView` | View must implement `IApplicationView` interface |
| 2 | `login_model.py` | class def | `LoginModel` inherits `None` (via `IApplicationModel = None` in base) | Model should inherit proper base class |

---

### 14. `modbus_settings`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `modbus_settings_controller.py` | class def | Inherits `BackgroundWorker` mixin instead of standard `IApplicationController` | Non-standard controller pattern; deviates from blueprint |

---

### 15. `pick_and_place_visualizer`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `pick_and_place_visualizer_factory.py` | `build()` | Does NOT inherit `ApplicationFactory`; uses `finalize_application_build` directly | Blueprint step 9: factory must inherit `ApplicationFactory` |
| 2 | `pick_and_place_visualizer_view.py` | imports | Imports `app_styles` instead of `pl_gui.settings.settings_view.styles` | View styling rule: always use shared style system |

---

### 16. `pick_target`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `pick_target_factory.py` | ~46 | `view._controller = controller` assigned manually in `build()` | Factory must NOT assign `view._controller` — base class owns this |
| 2 | `pick_target_controller.py` | `load()` | Subscribes `VisionTopics.VISION_TARGET_RESULT` but no `unsubscribe` in `stop()` | Every `subscribe` in `load()` must have matching `unsubscribe` in `stop()` |
| 3 | `stub_pick_target_service.py` | `_resolve()` | Uses hardcoded dummy values | Liskov Substitution: stub should return realistic test data |

---

### 17. `robot_settings`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | — | — | Missing `stub_robot_settings_service.py` entirely | Blueprint step 4: every application needs a stub service for tests |
| 2 | `robot_settings_controller.py` | class def | Inherits `BackgroundWorker` mixin | Non-standard controller pattern |
| 3 | `robot_settings_controller.py` | `load()` | Subscribes `RobotTopics.ROBOT_STATE` but no `unsubscribe` in `stop()` | Every `subscribe` in `load()` must have matching `unsubscribe` in `stop()` |
| 4 | `robot_settings_application_service.py` | `_update_robot_state()` | Uses `print()` for error logging | Should use proper `logging` module |

---

### 18. `tool_settings`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `tool_settings_factory.py` | `build()` | Accepts dual services (`settings_service`, `tool_service`) | Acceptable extension but should be documented; factory should only take `IMyService` |
| 2 | `tool_settings_view.py` | imports | Imports `app_styles` instead of `pl_gui.settings.settings_view.styles` | View styling rule: always use shared style system |
| 3 | `tool_settings_controller.py` | imports | Imports `IToolService` from `src.robot_systems.paint.contracts` | **Platform layer must not know about paint**; couples to specific robot system |

---

### 19. `user_management`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `user_management_factory.py` | `build()` | Overrides `_create_view` to raise `NotImplementedError`; builds view manually in `build()` | Blueprint: factory should implement `_create_model`, `_create_view`, `_create_controller` |
| 2 | `stub_user_management_service.py` | — | Uses `print()` instead of proper `logging` module | Code quality: use logging, not print |
| 3 | `user_management_model.py` | imports | Imports `UserSchema` from `src.robot_systems.paint.schema` | **Platform layer must not know about paint**; couples to specific robot system |

---

### 20. `work_area_settings`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `work_area_settings_controller.py` | class def | Inherits `BrokerSubscriptionMixin` — non-standard pattern | Blueprint: controller should implement `IApplicationController` directly |
| 2 | `work_area_settings_view.py` | imports | Imports `app_styles` instead of `pl_gui.settings.settings_view.styles` | View styling rule: always use shared style system |

---

### 21. `workpiece_editor`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `workpiece_editor_factory.py` | `build()` | Builds view manually in `build()` (schema requires dynamic model data) | Blueprint: factory should use `_create_model`, `_create_view`, `_create_controller` |
| 2 | `workpiece_editor_controller.py` | `load()` | Subscribes `WorkpieceTopics.WORKPIECE_SELECTED` but no `unsubscribe` in `stop()` | Every `subscribe` in `load()` must have matching `unsubscribe` in `stop()` |
| 3 | `workpiece_editor_view.py` | imports | Imports `app_styles` instead of `pl_gui.settings.settings_view.styles` | View styling rule: always use shared style system |

---

### 22. `workpiece_library`

| # | File | Line | Violation | Rule Broken |
|---|------|------|-----------|-------------|
| 1 | `workpiece_library_factory.py` | `build()` | Builds view manually in `build()` (schema requires dynamic model data) | Blueprint: factory should use `_create_model`, `_create_view`, `_create_controller` |
| 2 | `workpiece_library_view.py` | imports | Imports `app_styles` instead of `pl_gui.settings.settings_view.styles` | View styling rule: always use shared style system |

---

## Priority Fix Order

### Critical (fix first — causes runtime bugs)
1. **lambda in signal connections** — `glue_cell_settings` (GC drops callbacks → silent failures)
2. **Broker subscribe without unsubscribe** — `calibration_v2`, `pick_target`, `robot_settings`, `workpiece_editor` (callbacks fire on deleted Qt widgets → `RuntimeError`)
3. **Factory assigns `view._controller`** — `aruco_z_probe`, `pick_target` (base class already does this; duplicate or conflicts)

### High (architectural violations)
4. **View imports `app_styles` instead of `pl_gui` styles** — 10 applications (breaks shared style system)
5. **Platform coupled to paint robot system** — `tool_settings` (controller), `user_management` (model)
6. **Model/Controller bypasses service interface** — `calibration` (model), `calibration_v2` (controller)

### Medium (deviation from blueprint)
7. **Non-standard factories** — `calibration`, `calibration_v2`, `pick_and_place_visualizer`, `workpiece_editor`, `workpiece_library`
8. **Missing stub service** — `robot_settings`
9. **Broken stub** — `contour_matching_tester`
10. **Missing interface method in stub** — `hand_eye_calibration`
11. **Concrete class imported instead of interface** — `contour_matching_tester`, `hand_eye_calibration`
12. **Signal connections in `__init__`** — `device_control`, `intrinsic_calibration_capture`
13. **Non-standard controller mixin** — `modbus_settings`, `robot_settings`, `work_area_settings`
14. **Wrong base class inheritance** — `login`

### Low (code quality)
15. **`print()` instead of `logging`** — `robot_settings`, `user_management`

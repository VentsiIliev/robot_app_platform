# Robot System Platform — Refactoring & Extraction Report

**Date:** March 28, 2026  
**Scope:** `src/robot_systems/` (glue, paint, blueprint) vs. `src/engine/`  
**Purpose:** Identify all code that is duplicated across robot systems and can be extracted into reusable engine components — without making any changes yet.

---

## Executive Summary

After reading every file in both robot systems (`GlueRobotSystem`, `PaintRobotSystem`) and the `ROBOT_SYSTEM_BLUEPRINT`, six categories of **near-identical duplication** were found. Each category carries a clear extraction path into the engine layer. One additional category concerns the **bootstrap provider** which is structurally duplicated but simpler to deal with.

---

## Category 1 — Navigation Facade (`*NavigationService`)

### Duplicated files
| File | Lines |
|---|---|
| `src/robot_systems/glue/navigation.py` (`GlueNavigationService`) | ~135 |
| `src/robot_systems/paint/navigation.py` (`PaintNavigationService`) | ~135 |

### What they share (100 % identical)
- Constructor signature and body (`navigation`, `vision`, `robot_service`, `work_area_service`, `observed_area_by_group`)
- `_capture_z_offset` property
- `move_home()` — moves with z-offset, sets area to `"pickup"`
- `move_to_login_position()`
- `move_to_calibration_position()`
- `move_to()`, `move_linear()`, `move_to_group()`, `move_linear_group()`, `move_to_position()`
- `get_group_names()`, `get_group_position()`
- `_move_with_z_offset()` (private)
- `_set_area()`, `_set_observed_area_for_group()` (private)

### What differs
Nothing. The two classes are byte-for-byte identical except for their class names (`GlueNavigationService` vs `PaintNavigationService`) and the navigation import annotation in the `frames.py` helpers.

### Proposed extraction
Create `src/engine/robot/features/system_navigation_service.py` — a single `SystemNavigationService` class that replaces both. Both robot systems replace their local import with this engine class. The per-system navigation class files are deleted entirely.

---

## Category 2 — Targeting Provider (`*RobotSystemTargetingProvider`)

### Duplicated files
| File | Lines |
|---|---|
| `src/robot_systems/glue/targeting/provider.py` (`GlueRobotSystemTargetingProvider`) | ~130 |
| `src/robot_systems/paint/targeting/provider.py` (`PaintRobotSystemTargetingProvider`) | ~130 |

### What they share
- Constructor `__init__(self, robot_system)`
- `_settings_service()`, `_robot_config()` accessors (identical)
- `_targeting_settings()` — the only difference is the attribute name it falls back to: `_glue_targeting` vs `_paint_targeting`. This difference disappears if both robot systems store the targeting settings under a unified attribute name (e.g. `_targeting_settings_data`)
- `_frame_definitions()` — full merge logic for persisted + declared frames (100 % identical)
- `_point_definitions()` — full merge logic for persisted + declared points (100 % identical)
- `build_point_registry()` — delegates to a local `build_*_point_registry()` function
- `build_frames()` — delegates to a local `build_*_target_frames()` function, constructs `HeightCorrectionService`
- `get_frame_for_work_area()`, `get_work_area_for_frame()`, `get_target_options()`, `get_default_target_name()` (100 % identical)

### What differs
Only two things:
1. The fallback attribute for targeting settings (`_glue_targeting` / `_paint_targeting`)
2. The delegated module-level functions `build_glue_point_registry` / `build_paint_point_registry` and `build_glue_target_frames` / `build_paint_target_frames` — which are themselves also identical (see Category 3)

### Proposed extraction
Move all shared logic into a `DefaultRobotSystemTargetingProvider` in `src/engine/robot/targeting/` that takes a `robot_system` and a `targeting_settings_attr` string (default `"_targeting_settings_data"`). Both existing providers collapse to zero code — they can be deleted and replaced by direct instantiation of the engine class.

---

## Category 3 — Targeting Frame Builder and Point Registry Builder

### Duplicated files
| File | Lines |
|---|---|
| `src/robot_systems/glue/targeting/frames.py` (`build_glue_target_frames`) | ~52 |
| `src/robot_systems/paint/targeting/frames.py` (`build_paint_target_frames`) | ~52 |
| `src/robot_systems/glue/targeting/registry.py` (`build_glue_point_registry`) | ~30 |
| `src/robot_systems/paint/targeting/registry.py` (`build_paint_point_registry`) | ~30 |

### What they share
All four files are 100 % identical in logic. The only differences are:
- `frames.py`: the type annotation for the `navigation` parameter (`GlueNavigationService` vs `PaintNavigationService`) — which itself becomes `SystemNavigationService` after Category 1
- `registry.py`: the function name prefix (`build_glue_` vs `build_paint_`)

### Proposed extraction
Create two engine-level functions:
- `src/engine/robot/targeting/target_frame_builder.py` → `build_target_frames(frame_definitions, navigation, height_correction)`
- `src/engine/robot/targeting/point_registry_builder.py` → `build_point_registry(point_definitions)`

All four robot-system-level files are deleted and their call sites updated.

---

## Category 4 — Targeting Settings Adapter (`targeting/settings_adapter.py`)

### Duplicated files
| File | Lines |
|---|---|
| `src/robot_systems/glue/targeting/settings_adapter.py` | ~120 |
| `src/robot_systems/paint/targeting/settings_adapter.py` | ~120 |
| `src/robot_systems/ROBOT_SYSTEM_BLUEPRINT/targeting/settings_adapter.py` | ~120 |

### What they share
All three are 100 % identical. Both `to_editor_dict()` and `from_editor_dict()` functions accept the same arguments, follow the same merge/deepcopy logic, and return the same dict structure.

### Proposed extraction
Move to `src/engine/robot/targeting/settings_adapter.py` as a single canonical module. All three robot-system copies are deleted. The `_build_robot_settings_application()` wiring function in each `application_wiring.py` updates its import path.

This is the **highest-confidence, lowest-risk** extraction: it is pure functions, no state, no inheritance.

---

## Category 5 — Calibration Provider (`*RobotSystemCalibrationProvider`)

### Duplicated files
| File | Lines |
|---|---|
| `src/robot_systems/glue/calibration/provider.py` (`GlueRobotSystemCalibrationProvider`) | ~23 |
| `src/robot_systems/paint/calibration/provider.py` (`PaintRobotSystemCalibrationProvider`) | ~23 |

### What they share
Both implement one abstract method: `build_calibration_navigation()`. Both do exactly the same thing:
```python
def build_calibration_navigation(self):
    work_area_service = self._robot_system.get_service(CommonServiceID.WORK_AREAS)
    return CalibrationNavigationService(
        self._robot_system.get_service(CommonServiceID.NAVIGATION),
        before_move=(lambda: work_area_service.set_active_area_id("<primary_area_id>")),
    )
```

The **only** difference is the area ID string: `"spray"` (glue) vs `"spray"` (paint — also `"spray"`, not `"paint"`!). Interestingly, the paint provider also uses `"spray"` as the area ID, even though the paint system's primary work area is `"paint"`. This looks like a bug that should be fixed as part of this extraction.

### Proposed extraction
Extend `RobotSystemCalibrationProvider` in the engine with a concrete `DefaultRobotSystemCalibrationProvider` that accepts a `robot_system` and a `calibration_area_id` string. Both system-level providers collapse to direct instantiation. The apparent bug in `PaintRobotSystemCalibrationProvider` (using `"spray"` instead of `"paint"`) should be confirmed and corrected.

---

## Category 6 — Application Wiring Functions (Shared Standard Apps)

### Duplicated wiring functions
These functions appear in **all three** `application_wiring.py` files (glue, paint, blueprint) with identical bodies:

| Function | Glue | Paint | Blueprint | Notes |
|---|---|---|---|---|
| `_build_capture_snapshot_service()` | ✓ | ✓ | — | Identical |
| `_build_user_management_application()` | ✓ | ✓ | ✓ | Identical except user schema builder (`build_glue_user_schema` vs `build_paint_user_schema` vs `build_my_user_schema`) |
| `_build_camera_settings_application()` | ✓ | ✓ | ✓ | 100 % identical |
| `_build_calibration_settings_application()` | ✓ | ✓ | ✓ | 100 % identical |
| `_build_work_area_settings_application()` | ✓ | ✓ | ✓ | 100 % identical |
| `_build_robot_settings_application()` | ✓ | ✓ | ✓ | Near-identical; only difference is the `settings_adapter` import path (see Category 4) |
| `_build_calibration_application()` | ✓ | ✓ | — | Near-identical; only difference is `process_controller` source (`robot_system.coordinator` vs `robot_system._calibration_coordinator`) and the active area string `"spray"` vs `"paint"` |
| `_build_broker_debug_application()` | ✓ | ✓ | — | 100 % identical |
| `_build_tool_settings_application()` | ✓ | — | ✓ | 100 % identical |

### What differs in `_build_user_management_application()`
Only the user schema builder function call: `build_glue_user_schema`, `build_paint_user_schema`, `build_my_user_schema`. All three schema builders also produce **identical** output — they define the same five fields (`id`, `firstName`, `lastName`, `password`, `role`, `email`). The schema builder functions are themselves candidates for a single `build_standard_user_schema(role_values)` in the engine.

### Proposed extraction
Create `src/robot_systems/shared_application_wiring.py`:
- Move all identical standard application builder functions here
- `_build_user_management_application()` accepts an optional `user_schema_builder` parameter (default: `build_standard_user_schema`)
- Per-system `application_wiring.py` files delegate to the shared module and only define system-specific builders (dashboard, domain-specific screens)

This is the **highest-impact** extraction — it eliminates the majority of `application_wiring.py` duplication in one step.

---

## Category 7 — Bootstrap Provider (`*BootstrapProvider`)

### Duplicated files
| File | Lines |
|---|---|
| `src/robot_systems/glue/bootstrap_provider.py` (`GlueBootstrapProvider`) | ~50 |
| `src/robot_systems/paint/bootstrap_provider.py` (`PaintBootstrapProvider`) | ~50 |

### What they share
- `build_login_view()` — 100 % identical logic; only the user schema builder differs (same as Category 6)
- `build_authorization_service()` — 100 % identical

### What differs
- `system_class` property (different system class returned)
- `build_robot()` — both return `FairinoRos2Robot(server_url="http://localhost:5000")` — also identical. This is almost certainly a configuration concern rather than a per-system difference; the URL should come from a config file, not be hardcoded per robot system.

### Proposed extraction
Add default implementations of `build_login_view()` and `build_authorization_service()` directly into `RobotSystemBootstrapProvider` (the abstract base), since they are identical for all systems. The concrete providers only need to override `system_class` and `build_robot()`.

---

## Category 8 — User Schema Builder

### Duplicated files
| File |
|---|
| `src/robot_systems/glue/domain/users/glue_user_schema.py` (`build_glue_user_schema`) |
| `src/robot_systems/paint/domain/users/paint_user_schema.py` (`build_paint_user_schema`) |
| `src/robot_systems/ROBOT_SYSTEM_BLUEPRINT/domain/users/` (`build_my_user_schema`) |

### What they share
All three produce an identical `UserSchema` with the same six fields and the same widget types. The only parameter is `role_values: list[str]`.

### Proposed extraction
Create `src/engine/auth/standard_user_schema.py` → `build_standard_user_schema(role_values)`. All three per-system builders are deleted. Bootstrap providers and wiring functions update their imports.

---

## Dependency Map (what blocks what)

The extractions have a natural dependency order:

```
1. Category 3: Extract target_frame_builder + point_registry_builder  (no deps)
2. Category 4: Extract targeting/settings_adapter                     (no deps)
3. Category 8: Extract standard_user_schema                           (no deps)
4. Category 1: Extract SystemNavigationService                        (unblocks Cat 2, 3)
5. Category 2: Extract DefaultRobotSystemTargetingProvider            (depends on Cat 1, 3)
6. Category 5: Extract DefaultRobotSystemCalibrationProvider + fix bug (no deps)
7. Category 6: Extract shared_application_wiring                      (depends on Cat 4, 8)
8. Category 7: Lift common bootstrap logic into base class            (depends on Cat 8)
```

---

## Effort vs. Impact Matrix

| Category | Effort | Impact | Risk |
|---|---|---|---|
| 4 — Settings adapter | Low (pure functions, no state) | High (3 files → 1) | Very low |
| 8 — User schema | Low (trivial factory function) | Medium | Very low |
| 3 — Frame/registry builders | Low (pure functions) | Medium (4 files → 2) | Very low |
| 1 — Navigation facade | Low (class rename + move) | High (2 identical classes → 1) | Low |
| 5 — Calibration provider | Low (tiny provider + bug fix) | Low-Medium | Low |
| 7 — Bootstrap provider | Low (move methods to base) | Medium | Low |
| 2 — Targeting provider | Medium (merge logic → base class) | High | Low |
| 6 — Application wiring | Medium (refactor 3 files) | Very high (most duplication) | Medium |

---

## Summary Statistics

| Metric | Current | After all extractions |
|---|---|---|
| Total duplicated files | ~18 | ~0 |
| Duplicated lines of code | ~1,100 | ~0 |
| Unique engine additions needed | 0 | ~8 new files |
| Per-robot-system `targeting/` folders | 3 × 4 = 12 files | 3 × 0 = 0 (all deleted) |
| Shared `application_wiring.py` lines per system | ~200 shared | ~20 (system-specific only) |

---

## Bugs Found During Analysis

1. **`PaintRobotSystemCalibrationProvider.build_calibration_navigation()`** sets `before_move` to `work_area_service.set_active_area_id("spray")` — but the paint system's primary work area is `"paint"`, not `"spray"`. The glue system correctly uses `"spray"`. This should be `"paint"` in the paint provider and needs to be verified and corrected when implementing Category 5.

2. **`PaintNavigationService.move_home()`** sets the active area to `"pickup"` — but the paint system has no `"pickup"` work area. Its only work area is `"paint"`. This is the same class of bug as #1, inherited by copy-paste. This needs to be parametrised (the "home area" and "calibration area" should be constructor arguments, not hardcoded strings) when implementing Category 1.

---

## Files That Should NOT Be Extracted

The following are correctly system-specific and should remain per-robot-system:

- `*_robot_system.py` — the declaration itself, by design
- `application_wiring.py` entries for domain-specific apps (dashboard, glue/paint process drivers, workpiece editor, dispense channel settings)
- `service_builders.py` — hardware-specific service construction (weight cells, Modbus motors)
- `processes/` — domain-specific business logic
- `height_measuring/provider.py` — legitimately different (one uses real Modbus laser, one uses a mock)


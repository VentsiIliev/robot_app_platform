# Localization Adoption Plan

Date: 2026-05-08

## Goal

Make localization:

- easier to adopt in new applications
- cheaper to maintain across robot systems
- less error-prone during runtime language changes
- auditable with clear status and missing-work visibility

This plan is intentionally incremental. It improves the current JSON-based localization service rather than replacing it.

## Target Architecture

### 1. Keep Qt-native translation

Retain:

- `self.tr("...")` for widget-owned static strings
- `QCoreApplication.translate("Context", "...")` for controller-owned or dynamic strings
- `LocalizationService` as the single translator installer

This is already a defensible architecture and does not need a rewrite.

### 2. Support layered catalog roots

Current state:

- `LocalizationService` accepts a single `translations_dir`
- shared applications depend on robot-system-specific catalog copies

Target state:

- `LocalizationService` should accept multiple catalog roots in priority order
- merge order should be:
  1. shared platform or application catalogs
  2. robot-system catalogs
  3. selected language overlay on top of default language

Recommended API direction:

```python
LocalizationService(
    catalog_roots=[
        ".../src/applications",
        ".../src/robot_systems/glue/storage/translations",
    ],
    ...
)
```

Recommended catalog lookup model:

- shared app base catalogs live near the application code
- robot-system catalogs remain the place for domain-specific overrides

Suggested file shape:

```text
src/applications/login/localization/en.json
src/applications/login/localization/bg.json
src/applications/user_management/localization/en.json
src/applications/user_management/localization/bg.json
src/robot_systems/glue/storage/translations/en.json
src/robot_systems/glue/storage/translations/bg.json
```

Alternative if one-file-per-app feels too fragmented:

```text
src/applications/localization/en.json
src/applications/localization/bg.json
```

Preferred option:

- per-application catalogs for shared apps
- per-robot-system override catalogs for system-specific wording

Reason:

- ownership stays close to the code
- shared application strings stop being duplicated across robot systems
- robot systems can still override wording when needed

### 3. Standardize the view contract

Current problem:

- many views override `changeEvent()` only to call `on_language_changed()`
- `on_language_changed()` is often inherited from `AppWidget` and does nothing useful

Target state:

- every view has a real `retranslateUi()` method
- base classes call it consistently

Recommended changes:

1. Add a default no-op `retranslateUi()` to `IApplicationView`.
2. Let `IApplicationView` or `AppWidget` own the `LanguageChange` behavior once.
3. Remove duplicate `changeEvent()` overrides from views that only forward to `on_language_changed()`.
4. Use `retranslateUi()` as the required extension point for view text refresh.

Result:

- simpler view code
- no dead localization hooks
- easier onboarding for new applications

### 4. Standardize controller participation

Current problem:

- controller retranslation is ad hoc
- some controllers subscribe to `LocalizationTopics.LANGUAGE_CHANGED`
- some rely on custom view signals
- some do nothing

Target state:

- controllers only opt in when they own dynamic text or data-derived labels

Recommended base pattern:

- add an optional `on_language_changed()` method to `IApplicationController` or a reusable controller mixin
- expose a generic `language_changed = pyqtSignal()` from `IApplicationView`
- have the base view emit it during `LanguageChange`

Then a controller can do:

```python
self._view.language_changed.connect(self._retranslate)
```

Use the broker event only for non-Qt consumers.

Reason:

- views already receive `LanguageChange`
- controllers should not need broker plumbing just to refresh UI text

### 5. Localize shell metadata

Current problem:

- `FolderSpec` supports `translation_key`, but current robot systems mostly use raw `display_name`
- `ApplicationSpec` has no translation metadata

Target state:

- folders and app names are localizable at the shell layer

Recommended changes:

1. Use `FolderSpec.translation_key` consistently in all robot systems.
2. Extend `ApplicationSpec` with:
   - `display_name`
   - `translation_key`
3. Resolve translated application titles before shell registration.

Example:

```python
ApplicationSpec(
    name="UserManagement",
    display_name="User Management",
    translation_key="app.user_management",
    ...
)
```

### 6. Add audit tooling

Current problem:

- there is no automated way to see missing contexts or keys

Target state:

- one command should report:
  - contexts used in code
  - keys found in catalogs
  - missing keys
  - orphan catalog entries

Recommended tooling:

- add a small audit script under `tools/` or `scripts/`
- scan for:
  - `self.tr("...")`
  - `QCoreApplication.translate("Context", "...")`
- compare with JSON catalogs

This should become the standard verification step for localization work.

## Implementation Roadmap

### Phase 1: Foundation

1. Add multi-root catalog support to `LocalizationService`.
2. Add `retranslateUi()` to `IApplicationView`.
3. Add a base `language_changed` signal for views.
4. Add optional controller retranslation pattern.
5. Add localization audit script.

Expected outcome:

- no user-visible translation expansion yet
- lower cost for all future adoption

### Phase 2: Normalize Existing Partial Apps

Convert all `partial` applications to the standard pattern:

- replace dead `on_language_changed()` usage
- implement real `retranslateUi()`
- move raw strings behind `self.tr(...)` or controller `_t()`

Priority order:

1. `modbus_settings`
2. `device_control`
3. `robot_settings`
4. `glue_cell_settings`
5. `contour_matching_tester`
6. `pick_and_place_visualizer`
7. `glue_settings`
8. `dispense_channel_settings`
9. `glue_process_driver`

### Phase 3: Expand Coverage To Core Shared Apps

After the partial apps are normalized, adopt localization for the highest-value shared applications that are currently `none`.

Suggested order:

1. `camera_settings`
2. `work_area_settings`
3. `tool_settings`
4. `workpiece_library`
5. `workpiece_editor`
6. `calibration_settings`
7. `calibration`
8. `intrinsic_calibration_capture`
9. `height_measuring`
10. `pick_target`
11. `aruco_z_probe`
12. `hand_eye_calibration`
13. `broker_debug`

### Phase 4: Robot-System-Specific Dashboards

Add localization to:

- `paint` dashboard
- `welding` dashboard

This should happen after the shared infrastructure work, so those dashboards can use the same simplified pattern.

## Per-Application Plan

### Shared Applications

| Application | Current State | Target | Work Plan |
|---|---|---|---|
| `login` | actual in `glue` only | foundation reference app | Move shared strings into app-owned catalogs; keep controller `_t()` pattern |
| `user_management` | actual in `glue` only | foundation reference app | Move shared strings into app-owned catalogs; keep dynamic refresh; localize schema-driven labels through stable keys |
| `modbus_settings` | partial | actual | Add `retranslateUi()`, localize tab names, labels, action buttons, status messages |
| `device_control` | partial | actual | Localize title, device labels, ON/OFF buttons if desired, availability text, dynamic motor row labels where applicable |
| `glue_cell_settings` | partial | actual | Localize tab titles, cell labels, child tab widgets, save/tare actions, state labels |
| `robot_settings` | partial | actual | Localize tab names, group titles, movement/targeting editor labels, action buttons, dialog text |
| `contour_matching_tester` | partial | actual | Localize panel headers, capture state, matching summaries, table placeholders |
| `pick_and_place_visualizer` | partial | actual | Localize toolbar controls, state labels, step-mode labels, summaries, log panel header |
| `aruco_z_probe` | none | actual later | First normalize view pattern, then localize UI labels and workflow messages |
| `broker_debug` | none | optional actual | Low-priority internal tool; localize only if operators use it |
| `calibration` | none | actual later | Localize workflow phases, capture controls, preview dialogs, validation/error text |
| `calibration_settings` | none | actual later | Localize settings labels and save/apply workflow |
| `calibration_v2` | none | actual later or retire | Decide whether it is still active before investing in localization |
| `camera_settings` | none | actual | Good early candidate after partial apps; mostly form and button text |
| `hand_eye_calibration` | none | actual later | Localize step descriptions, buttons, status messages |
| `height_measuring` | none | actual later | Localize calibration flow, thresholds, status feedback |
| `intrinsic_calibration_capture` | none | actual later | Localize capture workflow and result/status text |
| `pick_target` | none | actual later | Localize probing controls, state labels, result text |
| `tool_settings` | none | actual | Localize settings forms and action labels |
| `work_area_settings` | none | actual | Localize form labels, tab names, and editor controls |
| `workpiece_editor` | none | actual later | Larger effort due editor surface area; localize major panels first |
| `workpiece_library` | none | actual | Localize list headers, actions, search/filter text, empty states |

### Robot-System-Specific Applications

| Application | Robot System | Current State | Target | Work Plan |
|---|---|---|---|---|
| `dashboard` | `glue` | actual | refine | Keep as reference implementation; move strings into app-owned/shared catalogs and reduce special-case controller wiring |
| `dispense_channel_settings` | `glue` | partial | actual | Add `retranslateUi()`, localize channel labels and save/apply text |
| `glue_process_driver` | `glue` | partial | actual | Localize process controls, status text, and validation messages |
| `glue_settings` | `glue` | partial | actual | Localize glue-type forms, tabs, dialogs, and state labels |
| `dashboard` | `paint` | none | actual later | Adopt simplified base view/controller pattern, then add dashboard catalog keys |
| `dashboard` | `welding` | none | actual later | Same as `paint` dashboard |

## Concrete Code Changes Recommended

### `src/engine/localization/`

Recommended changes:

1. Change `LocalizationService` to accept multiple catalog roots.
2. Preserve current fallback merge semantics.
3. Add helper methods for:
   - listing loaded roots
   - reporting missing catalogs
4. Keep `translate()` as a thin convenience wrapper.
5. Add a small audit utility module or script.

### `src/applications/base/`

Recommended changes:

1. Add `retranslateUi()` to `IApplicationView`.
2. Add `language_changed = pyqtSignal()` to the base view.
3. Emit `language_changed` from the base class on `LanguageChange`.
4. Stop requiring per-view boilerplate `changeEvent()` unless a view has special behavior.

### `src/shared_contracts/declarations/`

Recommended changes:

1. Extend `ApplicationSpec` with translation metadata for shell labels.
2. Use `FolderSpec.translation_key` consistently.

## Adoption Rules For New Applications

For every new application:

1. Put all widget-owned static strings behind `self.tr(...)`.
2. Implement `retranslateUi()` in the main view.
3. If the controller owns dynamic text, connect to `view.language_changed` and refresh there.
4. Add application-level catalog files near the application code.
5. Add robot-system overrides only for domain-specific wording.
6. Run the audit script before merging.

## Suggested First Execution Batch

If this work is implemented in code, the first batch should be:

1. refactor the localization foundation
2. convert `modbus_settings`
3. convert `device_control`
4. convert `robot_settings`
5. move `login` and `user_management` to app-owned shared catalogs

This gives one strong vertical slice:

- shared catalogs
- standardized view/controller pattern
- migrated real apps
- easier follow-on adoption

# Application Localization Audit

Date: 2026-05-08

## Scope

This audit covers:

- shared applications under `src/applications/`
- robot-system-specific applications under `src/robot_systems/*/applications/`
- the active runtime wiring through `src/bootstrap/main.py`

It distinguishes between:

- `actual`: the application both uses Qt translation APIs and has matching catalog coverage
- `partial`: the application has some localization hooks, but current catalogs or retranslation logic are incomplete
- `none`: no meaningful localization usage was found in the active application implementation
- `legacy`: translation-related code exists in files that do not appear to be part of the current MVC application path

## Runtime Summary

Localization is always bootstrapped in `src/bootstrap/main.py`, but catalogs are loaded from the active robot system's `metadata.translations_root`.

Current bootstrap:

- `PaintBootstrapProvider` is active in `src/bootstrap/main.py`

Catalog inventory in the repository:

- `src/robot_systems/glue/storage/translations/en.json`
- `src/robot_systems/glue/storage/translations/bg.json`
- `src/robot_systems/ROBOT_SYSTEM_BLUEPRINT/storage/translations/en.json`

Important consequence:

- with the current `paint` bootstrap, the application starts with a localization service, but there are no `paint` catalogs to provide translated strings
- today, no application is effectively translated at runtime when launching the default app configuration
- the only robot system with real multi-language catalog coverage is `glue`

## Main Findings

### 1. Only three application areas are actually localized today

When the `glue` robot system is active, these have real code-level localization plus matching catalog entries:

- `Login`
- `UserManagement` including `PermissionsView`
- `GlueDashboard` and its dashboard subwidgets

### 2. Several applications are localization-aware but not localized

These applications react to `QEvent.LanguageChange`, but they either:

- do not implement `retranslateUi()`
- do not override `on_language_changed()`
- or have no matching entries in robot-system catalogs

In practice, these are not localized today.

### 3. Many views contain dead localization hooks

A repeated pattern exists:

```python
def changeEvent(self, event) -> None:
    if event.type() == QEvent.Type.LanguageChange:
        self.on_language_changed()
    super().changeEvent(event)
```

In many views, `on_language_changed()` is inherited from `AppWidget` and only prints a debug line. That means the hook exists, but does not retranslate anything.

### 4. Shared applications depend on per-robot-system catalogs

The current catalog model lives entirely under `src/robot_systems/<system>/storage/translations/`. This makes shared application adoption more expensive because every system must copy the same shared application strings into its own catalog files.

### 5. Shell folder names are partially ready, app names are not

`FolderSpec` already supports `translation_key`, and `ShellConfigurator` passes it through to `pl_gui`. But the robot systems still mostly use raw `display_name`.

`ApplicationSpec` has no translation metadata today, so application names in the shell remain raw strings.

## Coverage Matrix

### Shared Applications

| Application | Status | Evidence | Catalog Coverage | Notes |
|---|---|---|---|---|
| `login` | `actual` in `glue`, `none` in current `paint` runtime | `LoginView.retranslateUi()`, `LoginController._t()` | `glue/en.json`, `glue/bg.json` | Properly wired, but only works with `glue` catalogs |
| `user_management` | `actual` in `glue`, `none` in current `paint` runtime | `UserManagementView.retranslateUi()`, `PermissionsView.retranslateUi()`, controllers refresh on language change | `glue/en.json`, `glue/bg.json` | Best example among shared apps |
| `modbus_settings` | `partial` | `changeEvent(LanguageChange)` only | none | No real retranslation implementation |
| `device_control` | `partial` | `changeEvent(LanguageChange)` only | none | Static labels/buttons still hard-coded |
| `glue_cell_settings` | `partial` | `changeEvent(LanguageChange)` only | none | Tab titles and child labels are not catalog-backed |
| `robot_settings` | `partial` | `changeEvent(LanguageChange)` only | none | Large amount of tab and group text remains raw |
| `contour_matching_tester` | `partial` | `changeEvent(LanguageChange)` only | none | Buttons, headers, summaries are hard-coded |
| `pick_and_place_visualizer` | `partial` | `changeEvent(LanguageChange)` only | none | Toolbar, states, summaries, logs are hard-coded |
| `aruco_z_probe` | `none` | no translation usage found | none | Adoption not started |
| `broker_debug` | `none` | no translation usage found | none | Adoption not started |
| `calibration` | `none` | no translation usage found | none | Adoption not started |
| `calibration_settings` | `none` | no translation usage found | none | Adoption not started |
| `calibration_v2` | `none` | no translation usage found | none | Adoption not started |
| `camera_settings` | `none` | no translation usage found | none | Adoption not started |
| `hand_eye_calibration` | `none` | no translation usage found | none | Adoption not started |
| `height_measuring` | `none` | no translation usage found | none | Adoption not started |
| `intrinsic_calibration_capture` | `none` | no translation usage found | none | Adoption not started |
| `pick_target` | `none` | no translation usage found | none | Adoption not started |
| `tool_settings` | `none` | no translation usage found | none | Adoption not started |
| `work_area_settings` | `none` | no translation usage found | none | Adoption not started |
| `workpiece_editor` | `none` | no translation usage found | none | Adoption not started |
| `workpiece_library` | `none` | no translation usage found | none | Adoption not started |

### Robot-System-Specific Applications

| Application | Robot System | Status | Evidence | Catalog Coverage | Notes |
|---|---|---|---|---|---|
| `dashboard` | `glue` | `actual` | `GlueDashboardController._t()`, `GlueMeterCard`, `SystemStatusWidget`, `DashboardPreviewWidget` | `glue/en.json`, `glue/bg.json` | Best end-to-end implementation |
| `dispense_channel_settings` | `glue` | `partial` | `changeEvent(LanguageChange)` only | none | Not yet catalog-backed |
| `glue_process_driver` | `glue` | `partial` | `changeEvent(LanguageChange)` only | none | Not yet catalog-backed |
| `glue_settings` | `glue` | `partial` | `changeEvent(LanguageChange)` only | none | Not yet catalog-backed |
| `dashboard` | `paint` | `none` | no translation usage found | none | No `paint` translation catalogs |
| `dashboard` | `welding` | `none` | no translation usage found | none | No `welding` translation catalogs |

### Templates And Legacy Code

| Area | Status | Notes |
|---|---|---|
| `APPLICATION_BLUEPRINT` | `partial template` | Shows `LanguageChange` hook but does not provide a full localization adoption recipe |
| `src/applications/user_management/ui/UserDashboard.py` | `legacy` | Uses a different localization mechanism and does not appear to be the active MVC path |
| `src/robot_systems/glue/applications/dashboard/localization/` | `legacy` | Contains older `.qm` / `.qts` assets that are separate from the active JSON catalog system |

## Structural Issues Observed

### Current Localization Service

Strengths:

- small surface area
- clear JSON catalog format
- clean fallback merge behavior
- publishes a broker event for non-widget consumers

Weak points:

- only one catalog root is supported
- shared applications cannot ship their own base catalogs
- translation coverage is hard to audit automatically
- the service does not help application authors with context naming or missing key discovery

### Current Application Usage Pattern

Strengths:

- `Login`, `UserManagement`, and `GlueDashboard` prove the model works
- Qt-native `self.tr(...)` and `QCoreApplication.translate(...)` are used correctly in the best examples

Weak points:

- no uniform base-class contract for `retranslateUi()`
- too many views rely on `on_language_changed()` with no override
- controller retranslation is inconsistent
- broker subscription is used ad hoc to notify controllers of language changes
- shell app names are not localized

## Recommended Direction

The current system should be improved, not replaced.

Recommended approach:

1. Keep the JSON + `QTranslator` architecture.
2. Add layered catalog roots so shared applications can ship base translations and robot systems can override them.
3. Standardize view retranslation through a real `retranslateUi()` contract on `IApplicationView`.
4. Add a base controller pattern for optional language-change handling.
5. Localize shell folders and application names using explicit translation keys.
6. Add tooling to detect missing catalog coverage.

The detailed implementation plan is in:

- `docs/engine/localization/localization_adoption_plan.md`

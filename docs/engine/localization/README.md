# `src/engine/localization/` — Runtime Localization

This package provides the platform-level localization mechanism. It wraps Qt's `QTranslator` with JSON catalogs and exposes a reusable engine service that any robot system can use.

The service is intentionally:
- engine-level
- reusable across robot systems
- localization-ready for both widget `self.tr(...)` strings and controller/presenter text

It does not depend on any specific robot system.

---

## Files

| File | Responsibility |
|------|----------------|
| [i_localization_service.py](/home/ilv/Desktop/robot_app_platform/src/engine/localization/i_localization_service.py) | Service contract: set/get language, available languages, translate |
| [dict_translator.py](/home/ilv/Desktop/robot_app_platform/src/engine/localization/dict_translator.py) | `QTranslator` subclass backed by JSON dictionaries |
| [localization_service.py](/home/ilv/Desktop/robot_app_platform/src/engine/localization/localization_service.py) | Catalog discovery, fallback merge, translator lifecycle, language-change event publishing |

---

## Architecture

```text
shared catalog root + robot-system metadata.translations_root
        ↓
bootstrap/main.py
        ↓
LocalizationService
        ├─ discovers available languages from all *.json roots
        ├─ merges default-language catalogs across roots
        ├─ overlays selected-language catalogs across roots
        ├─ installs one live QTranslator into Qt
        └─ publishes LocalizationTopics.LANGUAGE_CHANGED
        ↓
Qt widgets
        ├─ self.tr("...")
        └─ IApplicationView.on_language_changed() → retranslateUi() + language_changed
```

---

## Key Design Decisions

### 1. Catalogs are layered

Translations are now loaded from two roots:

- shared application catalogs under `src/applications/localization/`
- robot-system-specific catalogs under `src/robot_systems/<system>/storage/translations/`

Example:

```text
src/applications/localization/
  en.json
  bg.json
src/robot_systems/glue/storage/translations/
  en.json
  bg.json
```

Bootstrap resolves the active robot-system directory from:
- [SystemMetadata.translations_root](/home/ilv/Desktop/robot_app_platform/src/robot_systems/base_robot_system.py)

Shared catalogs load first. Robot-system catalogs load second and can override shared wording when needed.

### 2. Fallback language is merged, not chained

The service loads all default-language catalogs first, then overlays the selected language on top of that merged base.

Why:
- widget `self.tr(...)` fallback stays predictable
- partial translations work
- missing Bulgarian strings still show English instead of raw source text when English has an explicit catalog entry
- shared application strings can be reused by `paint`, `glue`, and `welding` without duplicating the same entries per system

### 3. Language changes are also published on the broker

`LocalizationService.set_language(...)` publishes:
- [LocalizationTopics.LANGUAGE_CHANGED](/home/ilv/Desktop/robot_app_platform/src/shared_contracts/events/localization_events.py)

This is useful for non-widget consumers later, such as presenters or controller-owned formatted text.

### 4. Selected language is persisted

The service stores the active language in a small JSON state file.

For the active robot system, bootstrap currently resolves the persisted state to:

```text
<robot_system module>/<metadata.settings_root>/localization.json
```

For glue, that becomes:

```text
src/robot_systems/glue/storage/settings/localization.json
```

On startup:
- `LocalizationService` loads the persisted language code if present
- bootstrap applies that language immediately
- bootstrap then synchronizes the shell selector to the resolved language

This avoids the startup mismatch where the selector showed one language while the UI was translated using another.

### 5. Views should use `self.tr(...)`

For static UI text in Qt widgets, prefer:

```python
self._save_btn.setText(self.tr("Save"))
```

This keeps translation native to Qt and works with `LanguageChange` events.

For standard shell applications that inherit `IApplicationView`, the default localization flow is now:

- Qt posts `QEvent.LanguageChange`
- `AppWidget.changeEvent(...)` calls `on_language_changed()`
- `IApplicationView.on_language_changed()` calls `retranslateUi()`
- `IApplicationView` emits `language_changed` for controllers that own dynamic text

That removes the need for most per-view `changeEvent(...)` boilerplate.

### 6. Controllers can use `QCoreApplication.translate(...)`

For dynamic controller text, use a stable context:

```python
QCoreApplication.translate("GlueDashboard", "Reset Errors")
```

That is how the dashboard controller currently re-translates action labels and pause/resume text.

For `IApplicationView`-based applications, prefer connecting controller retranslation to the base view signal:

```python
self._view.language_changed.connect(self._retranslate)
```

Use the broker `LocalizationTopics.LANGUAGE_CHANGED` event only when a non-Qt consumer needs to react.

### 7. Initial render and runtime retranslation are separate concerns

There are two different localization moments:

1. initial widget creation
2. later `QEvent.LanguageChange` updates

Qt only re-sends `LanguageChange` after a translator swap. That means:
- text created through `self.tr(...)` is translated correctly during initial widget construction if the translator is already installed
- text created from raw config strings or controller-owned strings is **not** translated automatically on first render

For those cases, controllers must do one explicit initial translation pass after the view is initialized.

The glue dashboard bug came from exactly this:
- action buttons were created from raw config labels in `pl_gui`
- they stayed English on startup
- they only became Bulgarian after a later language change

The fix was an explicit controller `_retranslate()` call from `_initialize_view()`.

---

## JSON Catalog Format

Top-level keys are Qt translation contexts.

`__meta__` is reserved for catalog metadata.

Example:

```json
{
  "__meta__": {
    "display_name": "English"
  },
  "GlueDashboard": {
    "Reset Errors": "Reset Errors",
    "Pick And Spray": "Pick And Spray"
  },
  "ControlButtonsWidget": {
    "Start": "Start",
    "Stop": "Stop",
    "Pause": "Pause"
  }
}
```

Bulgarian example:

```json
{
  "__meta__": {
    "display_name": "Български"
  },
  "GlueDashboard": {
    "Reset Errors": "Нулирай грешките",
    "Pick And Spray": "Вземи и пръскай"
  }
}
```

Rules:
- `__meta__.display_name` controls the language selector label
- each non-`__meta__` value must be a JSON object
- keys are source strings
- values are translated strings

---

## Runtime Wiring

Bootstrap now does this:

1. create `QApplication`
2. build `LocalizationService` from:
   - `src/applications/localization`
   - the active robot system's `translations_root`
3. set default language (`en`)
   or the persisted language if one was previously selected
4. pass `available_languages()` into `AppShell`
5. connect shell language selector to `localization_service.set_language`
6. synchronize the selector widget to `localization_service.get_language()`

`LanguageSelectorWidget` now posts `QEvent.LanguageChange` to top-level widgets and all descendant `QWidget`s. That matters because application views such as `UserManagementView` live inside the shell's stacked widget and are not top-level windows themselves.

---

## Step By Step

### Add a new language

1. Create a new file in a catalog root:

```text
src/applications/localization/de.json
```

or:

```text
src/robot_systems/<system>/storage/translations/de.json
```

2. Add metadata:

```json
"__meta__": { "display_name": "Deutsch" }
```

3. Copy the existing English contexts and translate values.

4. Restart the app.

The new language appears automatically in the shell selector because `LocalizationService.available_languages()` scans `*.json` across all configured roots.

### Add a new translatable string

1. Identify the Qt context.

Examples:
- widget class name when using `self.tr(...)`
- explicit context string when using `QCoreApplication.translate("Context", "...")`

2. Add the source string to `en.json`.

3. Add the translated value to other language catalogs.

4. In the code:
- widgets: use `self.tr("My String")`
- controllers/presenters: use `QCoreApplication.translate("MyContext", "My String")`

5. If the text is in a live widget, make sure it is refreshed on language change:
- either via existing widget `retranslateUi()`
- or via `changeEvent(QEvent.LanguageChange)`
- or for app views, via `on_language_changed()` if that view pattern is already used

6. If the text is **not** owned by a widget `self.tr(...)` call:
- retranslate it explicitly during initial screen setup
- retranslate it again when the language changes

Examples:
- action buttons built from raw config labels
- controller-managed pause/resume labels
- tab names built outside the widget itself
- notification titles/messages resolved in presenters

### Wire a new application

1. Make sure the robot system has `metadata.translations_root` pointing to its catalog directory.

2. In the view:
- use `self.tr(...)` for static labels, button text, placeholders, tab labels, etc.

3. If the view needs to update after language changes:
- implement `changeEvent(...)` and call `retranslateUi()`
- or use the existing `AppWidget.on_language_changed()` pattern already used in some views

Example:

```python
def retranslateUi(self) -> None:
    self._save_btn.setText(self.tr("Save"))
    self._title_lbl.setText(self.tr("Connection"))

def changeEvent(self, event) -> None:
    if event.type() == QEvent.Type.LanguageChange:
        self.retranslateUi()
    super().changeEvent(event)
```

4. If the controller owns dynamic text:
- re-read translations when the view emits its language-change signal
- use `QCoreApplication.translate("Context", "...")`

5. Add the new strings to the catalogs.

---

## Localization Checklist For Applications

Use this checklist whenever you add localization to a new or existing screen.

### A. Static widget-owned text

Use `self.tr(...)` in the widget:

```python
self._save_btn.setText(self.tr("Save"))
self._title_lbl.setText(self.tr("Connection"))
```

If the widget can stay open while language changes, add:

```python
def retranslateUi(self) -> None:
    self._save_btn.setText(self.tr("Save"))
    self._title_lbl.setText(self.tr("Connection"))

def changeEvent(self, event) -> None:
    if event.type() == QEvent.Type.LanguageChange:
        self.retranslateUi()
    super().changeEvent(event)
```

### B. Controller-owned or config-driven text

If the text is not created through `self.tr(...)`, the controller must own retranslation.

Pattern:

```python
def _initialize_view(self) -> None:
    ...
    self._retranslate()   # required initial pass

def _retranslate(self) -> None:
    self._view.set_action_button_text("reset", self._t("Reset Errors"))
    self._view.set_pause_text(self._t("Pause"))
```

And connect the view's language-change signal:

```python
self._view.language_changed.connect(self._retranslate)
```

Use a safe helper:

```python
@staticmethod
def _t(text: str) -> str:
    translated = QCoreApplication.translate("MyContext", text)
    return translated or text
```

The `or text` fallback is important because a custom translator returns `""` on a miss so Qt can continue its fallback chain.

### C. Catalog entries

For every translatable screen:
- add keys to `en.json`
- add translated values to other language catalogs
- keep context names stable

### D. Initial-load verification

Always verify both:
- opening the screen directly when the persisted language is already non-English
- changing the language live while the screen is open

These cover different code paths and both can fail independently.

---

## Dashboard Pilot

The first translated production slice is the glue dashboard.

Currently translated:
- dashboard action labels controlled by the controller
- system status labels and state badges
- glue meter card titles and state tooltips
- shared `ControlButtonsWidget` start/stop/pause labels from `pl_gui`

Important:
- `ControlButtonsWidget` works from `self.tr(...)` inside the widget
- dashboard action buttons require a controller `_retranslate()` call during initial load because they come from raw config labels

This is intentionally a pilot slice to validate the full path before translating the rest of the application set.

---

## Notes

- Missing catalogs are tolerated. The service falls back to the default language.
- Invalid JSON catalogs are logged and skipped.
- The service keeps a strong reference to the active translator so Qt does not lose it to GC.
- `translate(...)` is available on the service for non-widget text, but widgets should still prefer `self.tr(...)`.
- The persisted language state is intentionally tiny and separate from the main settings serializers, because it is platform/UI state rather than domain configuration.

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
robot_system metadata.translations_root
        ↓
bootstrap/main.py
        ↓
LocalizationService
        ├─ discovers available languages from *.json
        ├─ merges fallback language + selected language
        ├─ installs one live QTranslator into Qt
        └─ publishes LocalizationTopics.LANGUAGE_CHANGED
        ↓
Qt widgets
        ├─ self.tr("...")
        └─ changeEvent(LanguageChange) → retranslateUi() / on_language_changed()
```

---

## Key Design Decisions

### 1. Catalogs live per robot system

Translations belong to the robot system domain, not the engine.

Example:

```text
src/robot_systems/glue/storage/translations/
  en.json
  bg.json
```

The engine service reads the directory declared by:
- [SystemMetadata.translations_root](/home/ilv/Desktop/robot_app_platform/src/robot_systems/base_robot_system.py)

### 2. Fallback language is merged, not chained

The service loads the default language catalog first, then overlays the selected language on top of it into one merged translator.

Why:
- widget `self.tr(...)` fallback stays predictable
- partial translations work
- missing Bulgarian strings still show English instead of raw source text when English has an explicit catalog entry

### 3. Language changes are also published on the broker

`LocalizationService.set_language(...)` publishes:
- [LocalizationTopics.LANGUAGE_CHANGED](/home/ilv/Desktop/robot_app_platform/src/shared_contracts/events/localization_events.py)

This is useful for non-widget consumers later, such as presenters or controller-owned formatted text.

### 4. Selected language is persisted

The service stores the active language in a small JSON state file.

For the active robot system, bootstrap currently resolves it to:

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

### 6. Controllers can use `QCoreApplication.translate(...)`

For dynamic controller text, use a stable context:

```python
QCoreApplication.translate("GlueDashboard", "Reset Errors")
```

That is how the dashboard controller currently re-translates action labels and pause/resume text.

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
2. build `LocalizationService` from the active robot system's `translations_root`
3. set default language (`en`)
   or the persisted language if one was previously selected
4. pass `available_languages()` into `AppShell`
5. connect shell language selector to `localization_service.set_language`
6. synchronize the selector widget to `localization_service.get_language()`

The shell's `LanguageSelectorWidget` already posts `QEvent.LanguageChange` to top-level widgets, so normal Qt retranslation works without custom event plumbing in most views.

---

## Step By Step

### Add a new language

1. Create a new file in the robot system catalog directory:

```text
src/robot_systems/<system>/storage/translations/de.json
```

2. Add metadata:

```json
"__meta__": { "display_name": "Deutsch" }
```

3. Copy the existing English contexts and translate values.

4. Restart the app.

The new language appears automatically in the shell selector because `LocalizationService.available_languages()` scans `*.json`.

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

## Dashboard Pilot

The first translated production slice is the glue dashboard.

Currently translated:
- dashboard action labels controlled by the controller
- system status labels and state badges
- glue meter card titles and state tooltips
- shared `ControlButtonsWidget` start/stop/pause labels from `pl_gui`

This is intentionally a pilot slice to validate the full path before translating the rest of the application set.

---

## Notes

- Missing catalogs are tolerated. The service falls back to the default language.
- Invalid JSON catalogs are logged and skipped.
- The service keeps a strong reference to the active translator so Qt does not lose it to GC.
- `translate(...)` is available on the service for non-widget text, but widgets should still prefer `self.tr(...)`.
- The persisted language state is intentionally tiny and separate from the main settings serializers, because it is platform/UI state rather than domain configuration.

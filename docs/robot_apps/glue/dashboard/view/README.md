# `src/robot_apps/glue/dashboard/view/` — Glue Dashboard View

---

## `GlueDashboardView`

**File:** `glue_dashboard_view.py`

The main production dashboard widget. Extends `IPluginView` (which extends `AppWidget`). Displays per-cell `GlueMeterCard` widgets and a control row with Start/Stop/Pause/Action buttons.

### Outbound Signals

| Signal | Emitted when |
|--------|-------------|
| `start_requested` | User clicks Start |
| `stop_requested` | User clicks Stop |
| `pause_requested` | User clicks Pause/Resume |
| `action_requested(str)` | User clicks an action button (passes `action_id`) |
| `language_changed` | Qt `LanguageChange` event fires |

### Inbound Setters

| Method | Effect |
|--------|--------|
| `set_cell_weight(card_id, grams)` | Updates weight display on card `card_id` |
| `set_cell_state(card_id, state)` | Updates connection state indicator on card `card_id` |
| `set_cell_glue_type(card_id, glue_type)` | Updates glue type label on card `card_id` |
| `set_start_enabled(bool)` | Enables/disables the Start button |
| `set_stop_enabled(bool)` | Enables/disables the Stop button |
| `set_pause_enabled(bool)` | Enables/disables the Pause/Resume button |
| `set_pause_text(text)` | Changes Pause button label (e.g., "Pause" ↔ "Resume") |
| `set_action_button_text(action_id, text)` | Updates label on a named action button |
| `get_card(card_id)` | Returns the `GlueMeterCard` widget for `card_id` |

---

## `GlueMeterCard` (`ui/widgets/GlueMeterCard.py`)

Per-cell card widget. Displays:
- Cell label and glue type
- Live weight reading via `GlueMeterWidget` (analog gauge + numeric display)
- Connection state indicator
- "Change Glue" button

Emits `change_glue_requested(int)` with `card_id` when the user clicks Change Glue.

---

## `GlueMeterWidget` (`ui/widgets/GlueMeterWidget.py`)

Analog-style fill meter showing the current weight relative to cell capacity. Updated by `set_weight(value)` and `set_capacity(value)`.

---

## `GlueCardFactory` (`ui/factories/glue_card_factory.py`)

```python
class GlueCardFactory:
    def __init__(self, model: GlueDashboardModel): ...
    def build_cards(self, cell_configs: List[CardConfig]) -> List[GlueMeterCard]: ...
```

Builds one `GlueMeterCard` per `CardConfig` entry, pre-populating capacity and glue type from the model.

---

## Glue Change Wizard (`ui/glue_change_guide_wizard.py`)

```python
def create_glue_change_wizard(glue_type_names: List[str]) -> QWizard: ...
```

A 7-page `QWizard` guiding the operator through replacing a glue cartridge. The controller reads the selected glue type from `wizard.page(6).get_selected_option()` after `exec()` returns `Accepted`.

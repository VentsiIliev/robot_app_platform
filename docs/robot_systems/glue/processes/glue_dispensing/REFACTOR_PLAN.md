# Glue Dispensing State Machine — Refactor Plan

**Goal:** Break large states into smaller states that do less. Each state should have one job.

---

## Problem Analysis

### State Responsibility Audit

| State | Jobs | Problem |
|---|---|---|
| `STARTING` | 5 | God state — guard, resume routing, path skip loop, path loading, movement initiation |
| `WAIT_FOR_PATH_COMPLETION` | 2 | Dual personality — completely different impl based on runtime branch |
| `TRANSITION_BETWEEN_PATHS` | 2 | Hardware action + navigation decision mixed |
| `EXECUTING_PATH` | 1 | Fine, but the name is wrong — it only starts the generator |
| All others | 1 | Clean |

---

### Problem 1: `STARTING` is a god state

After the stop/pause guard, `STARTING` does **five different things**:

1. **Resume dispatch** — calls `_handle_resume()`, a large nested function with 4 code paths
2. **Completion check** — are we past the last path?
3. **Empty path skip** — self-loops `STARTING → STARTING` to skip empty entries
4. **Path loading** — copies `path`, `settings`, resets `current_point_index`
5. **Movement initiation** — calls `robot_service.move_ptp()`

The deepest issue is `_handle_resume()`. It encodes a completely separate workflow inside a helper function inside the normal-start handler. Resume and normal-start share a handler but have nothing in common beyond the guard. This is the hardest part to test in isolation and the first thing that will break if resume routing needs to change.

The `is_resuming: bool` context flag exists purely to distinguish the two workflows — a code smell that signals the two should be separate states.

---

### Problem 2: `WAIT_FOR_PATH_COMPLETION` has a dual personality

The handler dispatches at runtime between two completely different implementations:

```python
if pump_thread is not None:
    return _wait_via_pump_thread(...)   # polls thread.is_alive(), joins on stop/pause
return _wait_via_position_poll(...)      # polls robot position
```

These two modes have different:
- Completion signals (thread exit vs. distance threshold)
- Pause/stop behaviours (`join()` + result capture vs. just return)
- Progress capture logic

Both modes share the same state name, so logs and the transition table give no visibility into which mode is active.

---

### Problem 3: `TRANSITION_BETWEEN_PATHS` mixes hardware action with navigation

Sequentially does:
1. **Hardware**: stop the pump motor (with address resolution and error path → `ERROR`)
2. **Navigation**: increment `current_path_index`, decide `STARTING` vs. `COMPLETED`

These are conceptually separate phases. The pump-off step can go to `ERROR`; the index-advance step cannot. Mixing them means the error paths are harder to follow.

---

### Problem 4: `EXECUTING_PATH` has a misleading name

It only turns on the generator. It does not execute the path — that happens across `PUMP_INITIAL_BOOST`, `STARTING_PUMP_ADJUSTMENT_THREAD`, `SENDING_PATH_POINTS`, and `WAIT_FOR_PATH_COMPLETION`. A developer reading the state diagram for the first time will be confused by the name.

---

## The Plan

### Change 1 — Extract `RESUMING` state (highest value)

**What moves:** The entire `_handle_resume()` function, the `_EXECUTION_STATES` frozenset, and the `if context.is_resuming` branch leave `handle_starting.py` and become `handle_resuming.py`.

**Before:**
```
PAUSED → STARTING (is_resuming=True) → _handle_resume() dispatches to ...
```
**After:**
```
PAUSED → RESUMING → [MOVING_TO_FIRST_POINT | STARTING_GENERATOR | STARTING | COMPLETED | ERROR]
```

**Context change:** Remove `is_resuming: bool` — it's no longer needed. The state itself communicates intent.

**Files changed:**
- `handle_starting.py` — drop `_handle_resume`, `_EXECUTION_STATES`, and the `is_resuming` branch. Shrinks from ~96 lines to ~45 lines.
- `handle_paused.py` — `return S.STARTING` → `return S.RESUMING`. One line.
- `dispensing_context.py` — remove `is_resuming` field.
- New file: `handle_resuming.py`
- `dispensing_state.py` — add `RESUMING`
- `dispensing_machine_factory.py` — wire `RESUMING` handler

---

### Change 2 — Split `WAIT_FOR_PATH_COMPLETION` into two states (high value)

**What moves:** Each private function becomes its own state handler.

**Before:**
```
SENDING_PATH_POINTS → WAIT_FOR_PATH_COMPLETION  (dispatches internally)
```
**After:**
```
SENDING_PATH_POINTS → WAITING_FOR_PUMP_THREAD        (when pump_thread is not None)
SENDING_PATH_POINTS → WAITING_FOR_ROBOT_POSITION     (when pump_thread is None)
```

Both new states → `STOPPING_PUMP_BETWEEN_PATHS` on success.

**Files:**
- Delete `handle_wait_for_path_completion.py`
- New: `handle_waiting_for_pump_thread.py` (contains `_wait_via_pump_thread` + `_capture_pump_progress`)
- New: `handle_waiting_for_robot_position.py` (contains `_wait_via_position_poll`)
- `handle_sending_path_points.py` — routing changes: return `S.WAITING_FOR_PUMP_THREAD` or `S.WAITING_FOR_ROBOT_POSITION` based on `context.pump_thread`
- `dispensing_state.py` — add two new states, remove old one
- Transition table — update

---

### Change 3 — Split `TRANSITION_BETWEEN_PATHS` into two states (medium value)

**Before:**
```
TRANSITION_BETWEEN_PATHS: pump_off + index++ + route
```
**After:**
```
STOPPING_PUMP_BETWEEN_PATHS → ADVANCING_PATH
```

- `STOPPING_PUMP_BETWEEN_PATHS` — stops the pump (if `turn_off_pump=True` and `motor_started`). Always → `ADVANCING_PATH`. Can → `ERROR` on invalid motor address. Guard checks included.
- `ADVANCING_PATH` — increments `current_path_index`, resets `current_point_index = 0`, routes to `STARTING` or `COMPLETED`. Guard checks included.

**Files:**
- Delete `handle_transition_between_paths.py`
- New: `handle_stopping_pump_between_paths.py`
- New: `handle_advancing_path.py`
- `dispensing_state.py` — add two states, remove old one
- Transition table — update

---

### Change 4 — Rename `EXECUTING_PATH` → `STARTING_GENERATOR` (low effort, high clarity)

The state turns on the generator. The name should say so. Simple rename across:
- `dispensing_state.py` (enum value)
- `handle_executing_path.py` → rename file to `handle_starting_generator.py`
- `dispensing_machine_factory.py` (handler key)
- `handle_resuming.py` (references it as resume target)
- Transition table in `dispensing_state.py`

---

## New State Diagram (after all changes)

```
STARTING                        ← normal new-path load + move_ptp
  ↓
MOVING_TO_FIRST_POINT           ← poll position until arrival
  ↓
STARTING_GENERATOR              ← turn on generator (renamed from EXECUTING_PATH)
  ↓
PUMP_INITIAL_BOOST              ← ramp pump on
  ↓
STARTING_PUMP_ADJUSTMENT_THREAD ← launch background thread
  ↓
SENDING_PATH_POINTS             ← stream move_linear commands
  ↓ (branches on context.pump_thread)
WAITING_FOR_PUMP_THREAD         ← if pump_thread active
WAITING_FOR_ROBOT_POSITION      ← if no pump thread
  ↓
STOPPING_PUMP_BETWEEN_PATHS     ← pump_off (if configured)
  ↓
ADVANCING_PATH                  ← index++, detect completion
  ↓
STARTING (next path)  ─or─  COMPLETED

PAUSED → RESUMING               ← new state with the _handle_resume logic
RESUMING → MOVING_TO_FIRST_POINT | STARTING_GENERATOR | STARTING | COMPLETED | ERROR
```

---

## Unchanged States

`MOVING_TO_FIRST_POINT`, `PUMP_INITIAL_BOOST`, `STARTING_PUMP_ADJUSTMENT_THREAD`, `SENDING_PATH_POINTS`, `PAUSED`, `STOPPED`, `COMPLETED`, `ERROR`, `IDLE` — all clean, single-responsibility, no changes needed to their logic.

Minor mechanical touches only:
- `PAUSED` — one-line routing change (`return S.RESUMING` instead of `return S.STARTING`)
- `SENDING_PATH_POINTS` — updated return values to the two new wait states

---

## File Summary

| Action | Files |
|---|---|
| Add | `handle_resuming.py`, `handle_waiting_for_pump_thread.py`, `handle_waiting_for_robot_position.py`, `handle_stopping_pump_between_paths.py`, `handle_advancing_path.py` |
| Delete | `handle_wait_for_path_completion.py`, `handle_transition_between_paths.py` |
| Rename | `handle_executing_path.py` → `handle_starting_generator.py` |
| Shrink | `handle_starting.py` (drops ~50 lines of resume logic) |
| Minimal touch | `handle_paused.py`, `handle_sending_path_points.py`, `dispensing_state.py`, `dispensing_context.py`, `dispensing_machine_factory.py` |

---

## Implementation Order

Implement in sequence — each change is independently verifiable:

1. **Change 1** — Extract `RESUMING` (biggest complexity reduction)
2. **Change 2** — Split `WAIT_FOR_PATH_COMPLETION`
3. **Change 3** — Split `TRANSITION_BETWEEN_PATHS`
4. **Change 4** — Rename `EXECUTING_PATH` → `STARTING_GENERATOR`

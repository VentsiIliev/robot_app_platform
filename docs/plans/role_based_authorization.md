# Role-Based Authorization — Design Plan

## Context

The platform already has a `Role` enum (`ADMIN`, `OPERATOR`, `VIEWER`) and a `UserManagement`
application backed by a CSV repository. What's missing is:
- A login flow before the shell is shown
- A way for the admin to configure at runtime which roles can access each app
- A mechanism to filter `AppDescriptor`s before they reach `AppShell`

`pl_gui/` is treated as read-only — all filtering must happen before `AppShell` receives its
descriptor list. `AppShell.create_folders_page()` already drops any folder whose app list is
empty, so filtering at the descriptor level automatically hides empty folders too.

**Three resolved design decisions:**

| Decision | Choice | Rationale |
|---|---|---|
| First-run bootstrap | **"Create first admin" wizard — no default credentials** | A default `admin/admin` is a known attack vector |
| Role serialization | **`Role.value` strings** (`"Admin"`, `"Operator"`, `"Viewer"`) everywhere | Consistent with `User.to_dict()` / `User.from_dict()` already in the codebase |
| Permission keys | **`app_id: str` on `ApplicationSpec`** (camelCase→snake auto-derived) | Decouples display `name` from storage key |

---

## Architecture Overview

```
LoginWindow (QDialog)
       │ credentials / QR scan
       ↓
IAuthenticationService       ← "who are you?"       src/engine/auth/
  └─ AuthenticationService   ← bcrypt + lockout (internal, not on interface)
       │ returns Optional[User]
       ↓
UserSession (singleton)      ← holds current User + Role   src/engine/system/
       │
       ↓
IAuthorizationService        ← "what can you do?"    src/engine/auth/
  └─ AuthorizationService    ← depends on IPermissionsReader only (ISP)
       │ reads
       ↓
IPermissionsReader            ← minimal read interface   src/engine/auth/
IPermissionsRepository        ← extends reader + write   src/engine/auth/
  └─ PermissionsRepository   ← JSON impl                src/robot_systems/glue/
       │
       ↓
main.py                      ← visible_specs = authz.get_visible_apps(role, all_specs)
       ↓
AppShell                     ← receives pre-filtered descriptors (no changes needed)
```

---

## SOLID Principles Applied

| Principle | Decision |
|---|---|
| **S** — Single Responsibility | `IAuthenticationService` only verifies identity. `IAuthorizationService` only answers access questions (read-only). `UserManagementApplicationService` is the only place that enforces the "admin always keeps access" business rule — it is the write path. |
| **S** — Single Responsibility | `LoginApplicationService` contains auth only. Robot positioning for QR login is injected as `Callable[[], None]` from `main.py` — no robot imports in the login service. |
| **O** — Open/Closed | New auth methods (RFID, PIN) → new `IAuthenticationService` implementation, no interface change. New storage backend → new `IPermissionsRepository` implementation. |
| **L** — Liskov Substitution | `StubAuthenticationService` and `StubAuthorizationService` are drop-in replacements in all tests and standalone runners. |
| **I** — Interface Segregation | `IPermissionsReader` (get only) and `IPermissionsRepository(IPermissionsReader)` (get + set + list). `AuthorizationService` depends on `IPermissionsReader` — it never needs to write. `UserManagementApplicationService` depends on the full `IPermissionsRepository`. |
| **D** — Dependency Inversion | `AuthorizationService` (engine) depends on `IPermissionsReader` (engine interface) — never imports `PermissionsRepository` (glue). `LoginWindow` and `main.py` depend on interfaces, not concrete classes. Concrete wiring happens only in `application_wiring.py`. |

---

## Storage: `permissions.json`

**Path:** `src/robot_systems/glue/storage/settings/permissions.json`

Keys are `app_id` values (stable snake_case).
Values are `Role.value` string arrays — same serialization as `users.csv`.

```json
{
  "glue_dashboard":             ["Admin", "Operator", "Viewer"],
  "workpiece_editor":           ["Admin", "Operator"],
  "workpiece_library":          ["Admin", "Operator", "Viewer"],
  "robot_settings":             ["Admin"],
  "glue_settings":              ["Admin"],
  "modbus_settings":            ["Admin"],
  "cell_settings":              ["Admin"],
  "camera_settings":            ["Admin"],
  "device_control":             ["Admin"],
  "calibration":                ["Admin"],
  "tool_settings":              ["Admin"],
  "user_management":            ["Admin"],
  "broker_debug":               ["Admin"],
  "contour_matching_tester":    ["Admin"],
  "height_measuring":           ["Admin"],
  "pick_and_place_visualizer":  ["Admin"],
  "pick_target":                ["Admin"]
}
```

Any `app_id` not listed defaults to `["Admin"]` — safe fallback.

---

## Implementation Steps

### Step 1 — Add `app_id` to `ApplicationSpec`

**File:** `src/robot_systems/base_robot_system.py`

```python
import re

def _to_snake(name: str) -> str:
    """CamelCase → snake_case:  'GlueDashboard' → 'glue_dashboard'"""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

@dataclass(frozen=True)
class ApplicationSpec:
    name: str           # display name — may change freely
    folder_id: int
    icon: str = "fa5s.cog"
    factory: Optional[Callable] = field(default=None, compare=False)
    app_id: str = ""    # stable key for permissions.json — never change once set

    def __post_init__(self):
        if not self.app_id:
            object.__setattr__(self, "app_id", _to_snake(self.name))
```

All existing `ApplicationSpec(name="GlueDashboard", ...)` calls auto-derive
`app_id="glue_dashboard"` — **no changes needed to `glue_robot_system.py`**.

---

### Step 2 — `IAuthenticationService` + `AuthenticationService`

**New files:** `src/engine/auth/i_authentication_service.py`, `authentication_service.py`

```python
class IAuthenticationService(ABC):

    @abstractmethod
    def authenticate(self, user_id: str, password: str) -> Optional[User]:
        """Returns User on success, None on failure (including lockout)."""

    @abstractmethod
    def authenticate_qr(self, qr_payload: str) -> Optional[User]:
        """Decode QR payload → extract user_id + password → delegates to authenticate()."""
```

Throttling (failed-attempt counter, lockout timer) lives entirely inside
`AuthenticationService`. The interface stays clean — callers receive `None`, not a
lockout exception or error code.

**Stub:** `StubAuthenticationService` — accepts any credentials, returns a fixed `User`.

---

### Step 3 — `IPermissionsReader` + `IPermissionsRepository`

**ISP:** `AuthorizationService` only reads — it depends on the narrow `IPermissionsReader`.
`UserManagementApplicationService` reads and writes — it depends on the full `IPermissionsRepository`.

**New files:** `src/engine/auth/i_permissions_reader.py`, `i_permissions_repository.py`

```python
class IPermissionsReader(ABC):
    """Read-only interface. Used by AuthorizationService."""

    @abstractmethod
    def get_allowed_roles(self, app_id: str) -> List[Role]:
        """Defaults to [Role.ADMIN] if app_id is not found."""


class IPermissionsRepository(IPermissionsReader):
    """Full interface. Used by UserManagementApplicationService."""

    @abstractmethod
    def set_allowed_roles(self, app_id: str, roles: List[Role]) -> None:
        """Serializes as Role.value strings. Persists immediately."""

    @abstractmethod
    def get_all(self) -> Dict[str, List[Role]]:
        """Full map keyed by app_id — used by the admin permissions editor."""
```

**New file:** `src/robot_systems/glue/domain/permissions/permissions_repository.py`

Implements `IPermissionsRepository`. Serializes with `Role.value` strings — same pattern as
`User.to_dict()` / `User.from_dict()`. Unknown strings fall back to `Role.ADMIN`.

On load, auto-migrates the file: adds missing `app_id`s with `["Admin"]`, removes stale keys.

---

### Step 4 — `IAuthorizationService` + `AuthorizationService`

**New files:** `src/engine/auth/i_authorization_service.py`, `authorization_service.py`

```python
class IAuthorizationService(ABC):

    @abstractmethod
    def get_visible_apps(self, role: Role,
                         all_specs: List[ApplicationSpec]) -> List[ApplicationSpec]:
        """Filter specs to only those accessible by this role."""

    @abstractmethod
    def can_access(self, role: Role, app_id: str) -> bool:
        """Point check — for runtime guards inside apps."""
```

`AuthorizationService.__init__(self, reader: IPermissionsReader)` — depends on the narrow
read-only interface (ISP).

This service is **read-only**. It does not enforce business rules about which apps must always
be accessible — that is a write concern handled in `UserManagementApplicationService`.

**Stub:** `StubAuthorizationService` — all apps visible, `can_access` always `True`.

---

### Step 5 — `UserSession` singleton

**New file:** `src/engine/system/user_session.py`

```python
class UserSession:
    """Thread-safe singleton. Holds the currently logged-in user."""

    @classmethod
    def get(cls) -> 'UserSession': ...

    def login(self, user: User) -> None: ...
    def logout(self) -> None: ...

    @property
    def current_user(self) -> Optional[User]: ...

    @property
    def current_role(self) -> Optional[Role]: ...
```

---

### Step 6 — `LoginWindow` (`QDialog`)

**New file:** `src/applications/login/login_window.py`

Shown from `main.py` before `AppShell` is built. Not registered in `GlueRobotSystem.shell`.

**SRP:** `LoginApplicationService` handles auth only (`authenticate`, `authenticate_qr`).
Robot positioning is NOT in the service — it is injected into `QRLoginTab` as
`on_move_to_login_pos: Callable[[], None]` from `main.py`. If no robot is available,
pass a no-op — the QR tab degrades gracefully.

```
main.py
  │
  ├─ LoginApplicationService(auth_service: IAuthenticationService)
  │
  └─ LoginWindow(
         login_service: LoginApplicationService,
         on_move_to_login_pos: Callable[[], None]   ← injected from main.py
     )
```

#### 6a — First-run: "Create first admin" wizard

If `users.csv` is empty, show the wizard instead of the login tabs:
1. Fields: First Name, Last Name, numeric ID, Password, Confirm Password
2. Validate: all filled, passwords match
3. Hash password → write user with `Role.ADMIN` to CSV
4. Set `UserSession` immediately → proceed to shell (no separate login needed)

No default credentials are ever created.

#### 6b — Normal operation: dual-tab login

`QTabWidget`, two tabs, icon-driven (responsive sizing ~8% of window width):

**Tab 0 — Username / Password**
- `FocusLineEdit` for User ID (numeric, virtual keyboard)
- `FocusLineEdit` for Password (masked, virtual keyboard)
- `MaterialButton` → LOGIN
- Error feedback via `ToastWidget` (2 s)

**Tab 1 — QR Code**
- Safety warning on tab switch: *"Robot will move to login position — ensure area is clear"*
  → OK: calls injected `on_move_to_login_pos()` / CANCEL: reverts to Tab 0
- Live `CameraFeed` (640×360, 30 fps)
- `QTimer` polls every 2000 ms → `login_service.authenticate_qr(payload)` → `Optional[User]`
- On success: emergency-stop scanning → `UserSession.login(user)` → `dialog.accept()`
- Race-condition guards: `qr_scanning_active` flag + timer-active check + emergency stop
- On tab leave / window close: `force_stop_scanning()` + restore contour detection

#### 6c — Window behaviour
- ESC + close button disabled (`_allow_close` flag, only set after successful auth)
- Default tab configurable via `loginWindowConfig.json` (`DEFAULT_LOGIN: "NORMAL"` | `"QR"`)
- Layout: logo panel left (purple gradient) + `QStackedLayout` right

#### 6d — QR code generation (admin side — existing code, only needs UI wiring)

`UserManagementApplicationService.generate_qr(record)` already exists.
Add a **"Generate QR"** button per user row → calls it → optionally `send_access_package()`.
No new service code needed.

---

### Step 7 — Extend `UserManagement` with "App Permissions" tab

Add a second tab to the existing `UserManagement` application.

**SRP: business rule lives here.** `set_permissions()` enforces that `user_management`
always retains `Role.ADMIN` — this is the only write path, so it is the right place:

```python
def set_permissions(self, app_id: str, roles: List[Role]) -> None:
    if app_id == "user_management":
        roles = list(set(roles) | {Role.ADMIN})  # admin can never lose this app
    self._permissions_repo.set_allowed_roles(app_id, roles)
```

`IUserManagementService` gains two methods:
- `get_permissions() -> Dict[str, List[Role]]`
- `set_permissions(app_id: str, roles: List[Role]) -> None`

`UserManagementApplicationService` depends on `IPermissionsRepository` (full interface —
it reads and writes).

**Files:**
- `src/applications/user_management/service/i_user_management_service.py` — add two methods
- `src/applications/user_management/service/user_management_application_service.py` — implement
- `src/applications/user_management/view/user_management_view.py` — add permissions tab
- `src/robot_systems/glue/application_wiring.py` — inject `PermissionsRepository` into service

---

### Step 8 — Wire everything in `main.py`

`main.py` is the **composition root** — the only place where concrete classes are
instantiated and injected. All other code depends on interfaces.

```
1. EngineContext.build()
2. SystemBuilder ... .build(GlueRobotSystem)       ← robot_service available from here
3. ShellConfigurator.configure(GlueRobotSystem)
4. QApplication(sys.argv)
5. auth_service  = AuthenticationService(CsvUserRepository(users_path))
   login_service = LoginApplicationService(auth_service)
   move_to_pos   = lambda: robot_service.move_to_login_position()
   Show LoginWindow(login_service, on_move_to_login_pos=move_to_pos)  [blocking]
   ├─ First run? → "Create first admin" wizard → UserSession.login(user) → skip login
   ├─ SetupStepsWidget (onboarding) → NEXT
   ├─ Tab 0: Username + Password
   └─ Tab 1: QR auto-scan (camera + on_move_to_login_pos callback)
   → on success: UserSession.get().login(user)
6. perm_repo  = PermissionsRepository(permissions_path, known_app_ids)
   authz       = AuthorizationService(perm_repo)   ← IPermissionsReader only
7. visible_specs = authz.get_visible_apps(
       UserSession.get().current_role,
       GlueRobotSystem.shell.applications
   )
8. ApplicationLoader — load only visible_specs
9. AppShell — receives pre-filtered descriptors
```

---

## Critical Files

| File | Change |
|---|---|
| `src/robot_systems/base_robot_system.py` | Add `app_id` + `_to_snake()` to `ApplicationSpec` |
| `src/engine/auth/i_authentication_service.py` | **New** — `authenticate()`, `authenticate_qr()` |
| `src/engine/auth/authentication_service.py` | **New** — bcrypt + internal lockout |
| `src/engine/auth/i_permissions_reader.py` | **New** — narrow read interface (for `AuthorizationService`) |
| `src/engine/auth/i_permissions_repository.py` | **New** — full interface extending reader (for `UserManagementApplicationService`) |
| `src/engine/auth/i_authorization_service.py` | **New** — `get_visible_apps()`, `can_access()` |
| `src/engine/auth/authorization_service.py` | **New** — depends on `IPermissionsReader` only |
| `src/engine/system/user_session.py` | **New** — thread-safe session singleton |
| `src/robot_systems/glue/domain/permissions/permissions_repository.py` | **New** — JSON impl of `IPermissionsRepository` |
| `src/robot_systems/glue/storage/settings/permissions.json` | **New** — default permissions |
| `src/applications/login/login_window.py` | **New** — `QDialog`: wizard + dual-tab login |
| `src/applications/login/login_application_service.py` | **New** — auth only; no robot dependency |
| `src/applications/user_management/` | Add permissions tab; enforce admin-always rule in `set_permissions()` |
| `src/bootstrap/main.py` | Composition root: wires all services; shows login; filters specs |
| `src/robot_systems/glue/application_wiring.py` | Inject `PermissionsRepository` into `UserManagementApplicationService` |

---

## Key Design Decisions

- **AuthN/AuthZ separated**: two focused read-only interfaces, minimal surface area.
- **Throttling internal**: callers receive `None` — no lock-state leaks through the interface.
- **AuthZ is pure query**: `IAuthorizationService` never writes. Business rules live in the write path (`UserManagementApplicationService`).
- **ISP on permissions**: `AuthorizationService` depends only on `IPermissionsReader`; admin editing depends on the full `IPermissionsRepository`.
- **Robot positioning decoupled from auth**: injected as `Callable[[], None]` — `LoginApplicationService` has zero robot imports.
- **Layer integrity**: all interfaces in `src/engine/auth/`; glue implementations in `src/robot_systems/glue/`; concrete wiring only in `application_wiring.py` and `main.py`.
- **Safe defaults**: unknown `app_id` → `[Role.ADMIN]`; unknown role string → `Role.ADMIN`.

---

## Good Practices

### 1 — Password hashing
Store only bcrypt hashes in `users.csv`. `AuthenticationService` hashes on creation
and verifies with `bcrypt.checkpw()`. `CsvUserRepository` never sees plain text.

### 2 — Inactivity timeout / auto-logout
`QTimer` in a shell wrapper widget in `main.py` (not `pl_gui/`). Resets on any
mouse/keyboard event. On timeout: `UserSession.logout()` → hide shell → show
`LoginWindow` → rebuild `AppShell` with new role's filtered specs.

### 3 — Audit log
Append-only `audit.log` for every login, logout, and permission change:
```
2026-03-16 09:14:22 | user_id=3 | LOGIN       | role=Operator
2026-03-16 09:45:01 | user_id=1 | PERM_CHANGE | app=workpiece_editor roles=[Admin,Operator]
2026-03-16 10:02:15 | user_id=3 | LOGOUT      | reason=timeout
```

### 4 — Login throttling
Fully internal to `AuthenticationService` — N failures → account locked for M minutes.
`UserManagementApplicationService` exposes `reset_lockout(user_id)` for the admin.

### 5 — Logout button
Thin wrapper widget in `main.py` wrapping `AppShell`. On click: `UserSession.logout()`
→ re-show `LoginWindow` → rebuild shell with new role's filtered specs.

---

## Verification

1. Fresh install (no `users.csv`) → wizard appears → create admin → shell opens
2. Admin unchecks Operator from WorkpieceEditor → log in as Operator → app is gone
3. Admin tries to remove Admin from UserManagement → checkbox reverts → rule enforced
4. Delete `permissions.json` → restart → all apps default to Admin-only
5. Wrong password 5× → account locked → correct password still fails until timeout
6. Run: `python tests/run_tests.py` — all existing tests pass unchanged
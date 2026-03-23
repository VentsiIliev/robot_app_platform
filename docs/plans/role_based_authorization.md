# Role-Based Authorization — Design Plan

## Implementation Status

| Step | Description | Status |
|------|-------------|--------|
| 1 | `IAuthenticatedUser` — engine-level user base interface | ✅ Done |
| 2 | `IPermissionsRepository` + `PermissionsRepository` | ✅ Done |
| 3 | `IAuthorizationService` + `IPermissionsAdminService` + `AuthorizationService` | ✅ Done |
| 4 | `IAuthenticationService` + `AuthenticatedUser` + `AuthenticationService` | ✅ Done |
| 5 | Add `app_id` to `ApplicationSpec` | ✅ Done |
| 6 | `ISessionService` + `UserSession` | ✅ Done |
| 7 | Permissions migration (`ensure_permissions_current`) | ✅ Done |
| 8a | `ILoginApplicationService` + `LoginApplicationService` + `StubLoginApplicationService` | ✅ Done |
| 8b | `LoginWindow` — MVC login application (`LoginModel`, `LoginView`, `LoginController`, `LoginFactory`) | ✅ Done |
| 9 | Permissions editor in `UserManagement` (`PermissionsModel`, `PermissionsController`, `PermissionsView`, factory wiring) | ✅ Done |
| 10 | Filter specs at startup in `main.py` | ⬜ Pending |

---

## Context

The platform already has a `Role` enum (`ADMIN`, `OPERATOR`, `VIEWER`) and a `UserManagement` application backed by a CSV repository. What's missing is:
- A login flow before the shell is shown
- A way for the **admin to configure at runtime** which roles can access each app
- A mechanism to filter `AppDescriptor`s before they reach `AppShell`

`pl_gui/` is treated as read-only, so **all filtering must happen before `AppShell` receives its descriptor list**. `AppShell.create_folders_page()` already drops any folder whose `filtered_apps` list is empty — so filtering at the descriptor level automatically hides empty folders too.

**Four resolved design decisions:**

| Decision | Choice | Rationale |
|---|---|---|
| First-run bootstrap | **"Create first admin" wizard — no default credentials** | A default `admin/admin` is a known attack vector; forcing the operator to set their own password on first boot is safer and more explicit |
| Role serialization | **Role value strings defined by the robot system** | Shared auth and authorization work with strings and do not depend on a fixed global `Role` enum |
| Permission keys | **`app_id: str` field on `ApplicationSpec`** (stable snake_case) | Decouples the display `name` from the storage key — renaming a display name won't silently break `permissions.json` |
| Engine/app boundary | **`IAuthenticatedUser` at engine level** | Engine services (`IAuthenticationService`, `ISessionService`, `IAuthorizationService`) operate on this interface; application-level `User` implements it. No upward imports from engine into applications. |

---

## Architecture Overview

```
LoginWindow (QDialog)
       │ credentials / QR scan
       ↓
ILoginApplicationService              ← application-level service boundary
  └─ LoginApplicationService
       │ delegates auth ──────────→  IAuthenticationService
       │                               └─ AuthenticationService   (engine level)
       │                                    └─ IAuthUserRepository
       │                                         └─ AuthUserRepositoryAdapter
       │                                              └─ IUserRepository
       │                                                   └─ CsvUserRepository
       │ robot positioning ────────→  IRobotService
       │ QR scanning ──────────────→  ICameraService
       ↓
ISessionService                       ← holds current IAuthenticatedUser
  └─ UserSession (singleton)
       │
       ↓
IAuthorizationService                 ← read-only: get_visible_apps, can_access
IPermissionsAdminService              ← extends with get_all_permissions, set_permissions
  └─ AuthorizationService             (engine level — depends only on IPermissionsRepository)
       └─ IPermissionsRepository      ← engine-level interface
            └─ PermissionsRepository  (robot-system level — JSON-backed)
       │
       ↓
main.py filter                        ← visible_specs = authz.get_visible_apps(user, all_specs)
       ↓
AppShell                              ← receives pre-filtered descriptors (no changes needed)
```

**Authentication** answers: *"Are these credentials valid? Who is this user?"*
**Authorization** answers: *"Given this user's role, which apps are they allowed to see?"*
They are intentionally separate services with separate interfaces.

**Layer placement:**
- `IAuthenticatedUser`, `IAuthenticationService`, `IAuthorizationService`, `IPermissionsAdminService`, `IPermissionsRepository`, `ISessionService` → `src/engine/auth/` (Platform — Level 1)
- `AuthorizationService`, `UserSession` → `src/engine/auth/` (engine-level concrete, depends only on engine interfaces)
- `AuthenticationService`, `AuthenticatedUser`, `IAuthUserRepository`, `AuthUserRecord` → `src/engine/auth/` (Platform — Level 1)
- `PermissionsRepository` → `src/robot_systems/glue/` (RobotSystem — Level 2)
- `ILoginApplicationService`, `LoginApplicationService`, `LoginWindow` → `src/applications/login/` (Application — Level 3)

---

## Storage: `permissions.json`

**Path:** `<runtime_storage>/glue/settings/permissions.json`
(same runtime storage root used by all other settings files — not the `src/` tree)

Keys are `app_id` values (stable snake_case, never change even if display name changes).
Values are arrays of role value strings — consistent with how roles are stored in `users.csv`.

For the glue system, the default content is written on first run using its configured default permission role values:

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

### Step 1 — `IAuthenticatedUser`

**New file:** `src/engine/auth/i_authenticated_user.py`

```python
class IAuthenticatedUser(ABC):
    @property
    @abstractmethod
    def user_id(self) -> str:
        """Stable identifier for this user."""

    @property
    @abstractmethod
    def role(self) -> Enum:
        """The user's role. Compared via .value — no concrete Role type assumed."""
```

**Why:** Engine-level services must not import `User` or `Role` from the application layer.
All engine interfaces (`IAuthenticationService`, `ISessionService`, `IAuthorizationService`) operate exclusively on `IAuthenticatedUser`. The application-level `User` class implements this interface by adding `(IAuthenticatedUser)` as a base and exposing `user_id = property(lambda self: str(self.id))`.

---

### Step 2 — `IPermissionsRepository` + `JsonPermissionsRepository`

**New files:**
- `src/engine/auth/i_permissions_repository.py` — engine-level interface
- `src/engine/auth/json_permissions_repository.py` — reusable concrete implementation

```python
# src/engine/auth/i_permissions_repository.y_pixels
class IPermissionsRepository(ABC):

    @abstractmethod
    def get_allowed_role_values(self, app_id: str) -> List[str]:
        """Returns role value strings for this app_id.
        Defaults to the repository's configured default role values if missing."""

    @abstractmethod
    def set_allowed_role_values(self, app_id: str, role_values: List[str]) -> None:
        """Persists immediately. Caller is responsible for enforcing any robot-system-specific protected-role invariant."""

    @abstractmethod
    def get_all(self) -> Dict[str, List[str]]:
        """Full mapping keyed by app_id — used by the admin permissions editor."""
```

`JsonPermissionsRepository` implements this interface against a JSON file.
It works exclusively with `str` values — it never imports a concrete `Role` enum. Serialization and deserialization
use plain role value strings defined by the active robot system.

**Why:** `AuthorizationService` lives at the engine level and must not depend on a robot-system
concrete class. DIP — depend on the abstraction, not the implementation.

---

### Step 3 — `IAuthorizationService` + `IPermissionsAdminService` + `AuthorizationService`

**New files:**
- `src/engine/auth/i_authorization_service.py`
- `src/engine/auth/authorization_service.py`

```python
# Read-only interface — used by main.y_pixels and any runtime guard
class IAuthorizationService(ABC):

    @abstractmethod
    def get_visible_apps(self, user: IAuthenticatedUser, all_specs: List[ApplicationSpec]) -> List[ApplicationSpec]:
        """Filter specs to only those the given user's role may access."""

    @abstractmethod
    def can_access(self, user: IAuthenticatedUser, app_id: str) -> bool:
        """Single app check by stable app_id — used for runtime guards."""


# Extends with admin write operations — used only by the permissions editor
class IPermissionsAdminService(IAuthorizationService):

    @abstractmethod
    def get_all_permissions(self) -> Dict[str, List[str]]:
        """Full map keyed by app_id with role value strings — used by the permissions editor UI."""

    @abstractmethod
    def set_permissions(self, app_id: str, role_values: List[str]) -> None:
        """Admin updates role access for an app_id. Persisted immediately.
        Implementations may enforce robot-system-specific protected-role invariants."""
```

`AuthorizationService` implements `IPermissionsAdminService` (which extends `IAuthorizationService`).
Comparison inside is done on `user.role.value` — no import of `Role` needed.

**Caller access levels:**
- `main.py` holds `IAuthorizationService` — read-only, cannot call `set_permissions`
- Permissions editor model holds `IPermissionsAdminService` — full access

**Stub:** `StubAuthorizationService(IAuthorizationService)` — `get_visible_apps` returns all specs, `can_access` always `True`. Used in tests and standalone runners.

---

### Step 4 — `IAuthenticationService` + `IAuthUserRepository` + `AuthenticationService`

**New files:**
- `src/engine/auth/i_authentication_service.py` — engine-level interface
- `src/engine/auth/i_auth_user_repository.py` — thin auth-facing repository interface
- `src/engine/auth/auth_user_record.py` — minimal auth-facing user record
- `src/engine/auth/authentication_service.py` — reusable concrete implementation

```python
# src/engine/auth/i_authentication_service.y_pixels
class IAuthenticationService(ABC):

    @abstractmethod
    def authenticate(self, user_id: str, password: str) -> Optional[IAuthenticatedUser]:
        """Verify credentials. Returns IAuthenticatedUser on success, None on failure."""

    @abstractmethod
    def authenticate_qr(self, qr_payload: str) -> Optional[IAuthenticatedUser]:
        """Decode a QR payload and verify the embedded credentials."""
```

Lockout tracking (`record_failed_attempt`, `is_locked_out`) is **not on the interface** — it is an
internal implementation concern of `AuthenticationService`. No external caller should manipulate
lockout state directly.

`AuthenticationService` now lives at the engine level and depends only on `IAuthUserRepository`.
Robot systems can adapt richer user-management repositories to that thin auth contract with
`AuthUserRepositoryAdapter` while keeping CRUD-oriented schema logic outside the engine.

**Stub:** `StubAuthenticationService(IAuthenticationService)` — accepts any credentials, returns a
fixed `IAuthenticatedUser`. Used in tests and standalone runners.

---

### Step 5 — Add `app_id` to `ApplicationSpec`

**File:** `src/robot_systems/base_robot_system.py`

```python
@dataclass(frozen=True)
class ApplicationSpec:
    name: str           # display name, may change freely
    folder_id: int
    icon: str = "fa5s.cog"
    factory: Optional[Callable] = field(default=None, compare=False)
    app_id: str = ""    # stable snake_case key used in permissions.json — set once, never change
```

`__post_init__` auto-derives `app_id` from `name` if not provided:
```python
def __post_init__(self):
    if not self.app_id:
        object.__setattr__(self, "app_id", self.name.lower().replace(" ", "_"))
```

All existing `ApplicationSpec(name="GlueDashboard", ...)` calls auto-derive `app_id="glue_dashboard"` — **no changes needed to `glue_robot_system.py`**.

---

### Step 6 — `ISessionService` + `UserSession`

**New files:**
- `src/engine/auth/i_session_service.py`
- `src/engine/auth/user_session.py`

```python
# src/engine/auth/i_session_service.y_pixels
class ISessionService(ABC):

    @abstractmethod
    def login(self, user: IAuthenticatedUser) -> None: ...

    @abstractmethod
    def logout(self) -> None: ...

    @property
    @abstractmethod
    def current_user(self) -> Optional[IAuthenticatedUser]: ...

    @property
    @abstractmethod
    def current_role(self) -> Optional[Enum]: ...

    @abstractmethod
    def is_authenticated(self) -> bool: ...
```

`UserSession` implements `ISessionService`. Internally it is a singleton (one global instance),
but it is **always injected as `ISessionService`** — never accessed via `UserSession.get()` in
production code. `main.py` constructs the singleton once and passes it down.

Thread safety: a `threading.Lock` guards all reads and writes to `_current_user`.

**Why:** A bare singleton is a hidden global dependency that makes tests share mutable state.
Injecting `ISessionService` lets tests pass a `StubSessionService` with a preset user.

**Stub:** `StubSessionService(ISessionService)` — pre-loaded with a fixed `IAuthenticatedUser`.

---

### Step 7 — Permissions migration

**New file:** `src/engine/auth/permissions_migrator.py`

```python
def ensure_permissions_current(
    repo: IPermissionsRepository,
    known_app_ids: List[str],
) -> None:
    """
    Reconcile permissions.json against the live set of app_ids.
    - Adds missing app_ids with the robot system's configured default role values.
    - Removes keys for apps that no longer exist.
    - Saves back to disk only if changes were made.
    Called once in main.y_pixels after PermissionsRepository is built.
    """
```

**Why:** Loading data and migrating schema are separate responsibilities (SRP). The repository's
job is persistence — it loads and saves faithfully. Migration logic lives in its own function and
is called explicitly at startup. This keeps `PermissionsRepository.__init__` simple and
`ensure_permissions_current` independently testable.

---

### Step 8 — `ILoginApplicationService` + `LoginApplicationService` + `LoginWindow`

**New files:**
- `src/applications/login/i_login_application_service.py`
- `src/applications/login/login_application_service.py`
- `src/applications/login/stub_login_application_service.py`
- `src/applications/login/login_window.py`

```python
# src/applications/login/i_login_application_service.y_pixels
class ILoginApplicationService(ABC):

    @abstractmethod
    def authenticate(self, user_id: str, password: str) -> Optional[IAuthenticatedUser]: ...

    @abstractmethod
    def authenticate_qr(self, qr_payload: str) -> Optional[IAuthenticatedUser]: ...

    @abstractmethod
    def try_qr_login(self) -> Optional[Tuple[str, str]]:
        """Poll the camera for a QR code. Returns (user_id, password) or None."""

    @abstractmethod
    def move_to_login_pos(self) -> None:
        """Move robot to QR scan position."""

    @abstractmethod
    def is_first_run(self) -> bool:
        """True if users.csv is empty — setup wizard should be shown instead of login tabs."""

    @abstractmethod
    def create_first_admin(self, record: UserRecord) -> Tuple[bool, str]:
        """Create the initial admin user on first run. Returns (success, message)."""
```

`LoginApplicationService` wraps `IAuthenticationService` and adds robot/camera operations.
It is the **only** point where `LoginWindow` touches business logic.
`LoginWindow` depends only on `ILoginApplicationService` — fully testable with the stub.

**`LoginWindow`** is a `QDialog` subclass — shown from `main.py` before `AppShell` is built.
Not registered in `GlueRobotSystem.shell`.

#### 8a — Setup Wizard step (first run / onboarding)

Before the login tabs appear, a `SetupStepsWidget` is shown full-width:
- Displays a machine/instruction image + translatable instructions text
- **NEXT** button → transitions to the login tabs
- Optional: poll for a physical hardware button press (`check_physical_button()` on 500ms `QTimer`)
- **First-run detection**: calls `service.is_first_run()` — if `True`, replace login tabs with
  a "Create first admin" wizard (collect name, ID, password → `service.create_first_admin(record)`
  → set session → proceed). No default credentials ever created.

#### 8b — Login tabs (two methods)

`QTabWidget` with two tabs, icon-driven (responsive icon sizing: 30–80px, ~8% of window width):

**Tab 0 — Username / Password**
- `FocusLineEdit` for User ID (numeric only, virtual keyboard support)
- `FocusLineEdit` for Password (masked echo, virtual keyboard support)
- `MaterialButton` → LOGIN
- Error feedback via `ToastWidget` (2-second display)
- Validation: both fields required, ID must be digits
- Error codes: empty fields / non-numeric ID / wrong credentials / user not found

**Tab 1 — QR Code**
- **Safety warning dialog** on tab switch: *"Robot will move to login position — ensure area is clear"* → OK / CANCEL
- On OK: calls `service.move_to_login_pos()`
- On CANCEL: reverts silently to Tab 0
- Live `CameraFeed` widget (640×360, 30 fps)
- `QTimer` polls every 2000ms → `service.try_qr_login()` → returns `(user_id, password)` or None
- On detection: emergency-stop scanning → `service.authenticate(user_id, password)` → proceed
- Multiple race-condition guards: `qr_scanning_active` flag + timer-active check + emergency stop
- On window close or tab switch away: `force_stop_scanning()` + restore contour detection

#### 8c — Window behaviour
- ESC key and window close button **disabled** (`_allow_close` flag, only set `True` after successful auth)
- Default tab (Normal or QR) configurable via `loginWindowConfig.json` (`DEFAULT_LOGIN: "NORMAL"` or `"QR"`)
- Layout: logo panel left (purple gradient, responsive scaling) + login panel right (`QStackedLayout`)
- On success: `session_service.login(user)` → `dialog.accept()` → `main.py` proceeds

#### 8d — QR code generation (admin side — existing feature, just needs wiring)

`UserManagementApplicationService.generate_qr(record)` already generates a per-user QR image.
Wire a **"Generate QR"** button per user row in the `UserManagement` view that:
1. Calls `generate_qr(record)` → saves QR image to disk
2. Optionally calls `send_access_package(record, qr_path)` → emails it to the user

No new service code needed — only a UI button in `user_management_view.py`.

---

### Step 9 — Permissions editor in `UserManagement`

Extend the existing `UserManagement` application with a second tab: **"App Permissions"**.

The tab shows a table:

| App | Admin | Operator | Viewer |
|-----|-------|----------|--------|
| GlueDashboard | ✅ | ✅ | ✅ |
| WorkpieceEditor | ✅ | ✅ | ☐ |
| RobotSettings | ✅ | ☐ | ☐ |
| ... | | | |

Each checkbox calls `IPermissionsAdminService.set_permissions(app_id, role_values)` — using
the stable `app_id`, not the display name.

`IUserManagementService` is **not modified**. The permissions tab model/controller receives
`IPermissionsAdminService` as a separate constructor argument, injected in `application_wiring.py`.

Changes take effect on next login. The UI shows a notice: *"Changes apply at next login."*

**Files to modify:**
- `src/applications/user_management/view/user_management_view.py` — add tab widget
- `src/applications/user_management/model/user_management_model.py` — add permissions model
- `src/applications/user_management/controller/user_management_controller.py` — wire permissions tab
- `src/robot_systems/glue/application_wiring.py` — inject `IPermissionsAdminService` into the factory

**`IUserManagementService` is not modified** — user CRUD and permission management are separate
responsibilities with separate interfaces.

---

### Step 10 — Filter specs at startup in `main.py`

**File:** `src/bootstrap/main.py`

Modified startup sequence:
```
1.  EngineContext.build()
2.  SystemBuilder ... .build(GlueRobotSystem)
3.  ShellConfigurator.configure(GlueRobotSystem)
4.  QApplication(sys.argv)
5.  Build JsonPermissionsRepository(permissions_path)
6.  ensure_permissions_current(repo, known_app_ids)        ← migration, once at startup
7.  Build AuthorizationService(repo)                       ← IPermissionsAdminService
8.  Build UserSession()                                    ← ISessionService
9.  Build LoginApplicationService(auth_service, robot_system)
10. Show LoginWindow(login_service, session_service)       ← blocking QDialog
    ├─ SetupStepsWidget (onboarding / first-run wizard)
    ├─ Tab 0: Username + Password login
    └─ Tab 1: QR code auto-scan login (camera + robot positioning)
    → on success: session_service.login(user)
11. visible_specs = authz.get_visible_apps(session.current_user, all_specs)
12. ApplicationLoader — load only visible specs
13. AppShell — receives pre-filtered descriptors
```

---

## Critical Files

| File | Change |
|------|--------|
| `src/engine/auth/i_authenticated_user.py` | **New** — engine-level user base interface |
| `src/engine/auth/i_authentication_service.py` | **New** — authentication interface (returns `IAuthenticatedUser`) |
| `src/engine/auth/i_auth_user_repository.py` | **New** — thin auth repository interface |
| `src/engine/auth/auth_user_record.py` | **New** — minimal auth-facing user record |
| `src/engine/auth/authenticated_user.py` | **New** — default `IAuthenticatedUser` wrapper |
| `src/engine/auth/authentication_service.py` | **New** — reusable auth implementation via `IAuthUserRepository` |
| `src/engine/auth/i_permissions_repository.py` | **New** — permissions persistence interface (strings only, no `Role` import) |
| `src/engine/auth/i_authorization_service.py` | **New** — read-only authorization interface |
| `src/engine/auth/i_permissions_admin_service.py` | **New** — extends `IAuthorizationService` with admin write operations |
| `src/engine/auth/authorization_service.py` | **New** — implements `IPermissionsAdminService` via `IPermissionsRepository` |
| `src/engine/auth/i_session_service.py` | **New** — session interface |
| `src/engine/auth/user_session.py` | **New** — thread-safe singleton implementing `ISessionService` |
| `src/applications/user_management/domain/auth_user_repository_adapter.py` | **New** — adapts `IUserRepository` to `IAuthUserRepository` |
| `src/engine/auth/json_permissions_repository.py` | **New** — JSON-backed `IPermissionsRepository` implementation |
| `src/engine/auth/permissions_migrator.py` | **New** — `ensure_permissions_current()` migration function |
| `src/robot_systems/glue/storage/settings/permissions.json` | **New** — default permissions config |
| `src/robot_systems/base_robot_system.py` | Add `app_id: str` field to `ApplicationSpec` with auto-derive in `__post_init__` |
| `src/bootstrap/main.py` | Show login first, run migration, filter specs via `IAuthorizationService` |
| `src/applications/login/i_login_application_service.py` | **New** — login service interface |
| `src/applications/login/login_application_service.py` | **New** — wraps `IAuthenticationService`, adds `try_qr_login()` + `move_to_login_pos()` |
| `src/applications/login/stub_login_application_service.py` | **New** — test/standalone stub |
| `src/applications/login/login_window.py` | **New** — `QDialog` with setup wizard + dual-tab login |
| `src/applications/user_management/` | Add "App Permissions" tab; inject `IPermissionsAdminService` separately |
| `src/robot_systems/glue/application_wiring.py` | Wire all new concrete services with their dependencies |

---

## Key Design Decisions

- **No layer violations**: engine interfaces operate on `IAuthenticatedUser` and `IPermissionsRepository`; concrete types (`User`, `CsvUserRepository`, `PermissionsRepository`) stay at application/robot-system level.
- **ISP — two authorization interfaces**: `IAuthorizationService` (read-only, used by `main.py`) and `IPermissionsAdminService` (extends with write ops, used only by the permissions editor). No caller gets more power than it needs.
- **ISP — `IUserManagementService` unchanged**: user CRUD and permission management are separate concerns with separate interfaces. The permissions tab injects `IPermissionsAdminService` directly.
- **ISP — lockout is internal**: `record_failed_attempt` / `is_locked_out` are not on `IAuthenticationService`. Lockout is an implementation detail of `AuthenticationService`, not a contract for callers.
- **DIP — `UserSession` injected as `ISessionService`**: never accessed via a bare `UserSession.get()` global in production code. Tests pass a `StubSessionService`.
- **SRP — migration is separate from persistence**: `PermissionsRepository` loads and saves faithfully; `ensure_permissions_current()` handles schema reconciliation and is called once at startup.
- **Admin-configurable at runtime**: no code changes needed to adjust who can see what — the protected roles and default roles come from the robot system, and admins edit the resulting permissions via the UI.
- **Safe default**: any app not listed in `permissions.json` defaults to the robot system's configured default permission role values — including newly added apps.
- **Changes take effect on next login**: simplest approach; no need to rebuild `AppShell` at runtime.
- **No `pl_gui/` changes**: filtering happens before `AppShell`, which already handles empty folders.

---

## Verification

1. Log in as ADMIN → open UserManagement → "App Permissions" tab → uncheck Operator from WorkpieceEditor → save
2. Log out, log in as OPERATOR → verify WorkpieceEditor is gone from the shell
3. Log in as ADMIN again → re-enable → log in as OPERATOR → verify it's back
4. Delete `permissions.json` → restart → verify all apps default to the configured default permission roles
5. Add a new `ApplicationSpec` to `GlueRobotSystem.shell` without updating `permissions.json` → verify it gets the configured default roles
6. Run: `python tests/run_tests.py` — all existing tests pass unchanged

---

## Additional Good Practices

### 1 — Password hashing
Passwords must never be stored in plain text in `users.csv`. Use `bcrypt` or `argon2-cffi` to hash
on creation and verify on login. The `CsvUserRepository` should store only the hash; `AuthenticationService`
compares via `bcrypt.checkpw()`. Existing plain-text passwords need a migration strategy (e.g.
re-hash on first successful plain-text login, then overwrite the stored value).

### 2 — Login attempt throttling
After N consecutive failed logins (e.g. 5), lock the account for M minutes. Tracked entirely inside
`AuthenticationService` — not exposed on the interface. `IUserManagementService` should expose
`reset_lockout(user_id)` for the admin to unblock a user manually.

### 3 — Inactivity timeout / auto-logout
For an industrial robot platform, an unattended logged-in session is a safety risk. Add a `QTimer`
that resets on any mouse/keyboard event. On timeout: call `session_service.logout()`, hide `AppShell`,
re-show `LoginWindow`, then rebuild with the new role's filtered specs on success.

### 4 — Audit log
Record every login, logout, and permission change to an `audit.log` file (append-only).
Minimum fields: `timestamp | user_id | action | detail`.

```
2026-03-16 09:14:22 | user_id=3  | LOGIN        | role=Operator
2026-03-16 09:45:01 | user_id=1  | PERM_CHANGE  | app=WorkpieceEditor roles=[Admin,Operator]
2026-03-16 10:02:15 | user_id=3  | LOGOUT       | reason=timeout
```

### 5 — Logout button in shell
The shell header/toolbar should have a logout button visible to all users. Since `pl_gui/` is
read-only, this button lives in a thin wrapper widget created in `main.py` that wraps `AppShell`.
On click: `session_service.logout()` → hide shell → show `LoginWindow` → rebuild with new role's
filtered specs.

### 6 — Protected roles are system policy
`set_permissions()` in `AuthorizationService` can enforce protected app-role mappings injected by
the robot system. For glue, `user_management` always retains `"Admin"` regardless of what is passed
in. This is the single enforcement point — not duplicated in the repository.

```python
def set_permissions(self, app_id: str, role_values: List[str]) -> None:
    protected_roles = self._protected_app_role_values.get(app_id, [])
    if protected_roles:
        role_values = list(set(role_values) | set(protected_roles))
    self._repo.set_allowed_role_values(app_id, role_values)
```

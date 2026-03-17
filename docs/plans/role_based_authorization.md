# Role-Based Authorization — Design Plan

## Context

The platform already has a `Role` enum (`ADMIN`, `OPERATOR`, `VIEWER`) and a `UserManagement` application backed by a CSV repository. What's missing is:
- A login flow before the shell is shown
- A way for the **admin to configure at runtime** which roles can access each app
- A mechanism to filter `AppDescriptor`s before they reach `AppShell`

`pl_gui/` is treated as read-only, so **all filtering must happen before `AppShell` receives its descriptor list**. `AppShell.create_folders_page()` already drops any folder whose `filtered_apps` list is empty — so filtering at the descriptor level automatically hides empty folders too.

**Three resolved design decisions:**

| Decision | Choice | Rationale |
|---|---|---|
| First-run bootstrap | **"Create first admin" wizard** — no default credentials | A default `admin/admin` is a known attack vector; forcing the operator to set their own password on first boot is safer and more explicit |
| Role serialization | **`Role.value` strings** (`"Admin"`, `"Operator"`, `"Viewer"`) everywhere | Consistent with the existing `User.to_dict()` / `User.from_dict()` pattern already in the codebase |
| Permission keys | **`app_id: str` field on `ApplicationSpec`** (stable snake_case) | Decouples the display `name` from the storage key — renaming a display name won't silently break `permissions.json` |

---

## Architecture Overview

```
LoginWindow (QDialog)
       │ credentials / QR scan
       ↓
IAuthenticationService               ← "who are you?"
  └─ AuthenticationService
       │ returns Optional[User]
       ↓
UserSession (singleton)              ← holds current User + Role
       │
       ↓
IAuthorizationService                ← "what can you do?"
  └─ AuthorizationService
       │ asks PermissionsRepository
       ↓
PermissionsRepository (JSON)         ← maps app_id → [Role.value strings], admin-editable
       │
       ↓
main.py filter                       ← visible_specs = authz.get_visible_apps(role, all_specs)
       ↓
AppShell                             ← receives pre-filtered descriptors (no changes needed)
```

**Authentication** answers: *"Are these credentials valid? Who is this user?"*
**Authorization** answers: *"Given this user's role, which apps are they allowed to see?"*
They are intentionally separate services with separate interfaces.

---

## Storage: `permissions.json`

**Path:** `src/robot_systems/glue/storage/settings/permissions.json`

Keys are `app_id` values (stable snake_case, never change even if display name changes).
Values are arrays of `Role.value` strings — consistent with how roles are stored in `users.csv`.

Default content (generated on first run if missing, defaulting to Admin-only for safety):

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

### Step 1 — `IAuthenticationService` + `AuthenticationService`

**New files:**
- `src/engine/auth/i_authentication_service.py`
- `src/engine/auth/authentication_service.py`

```python
class IAuthenticationService(ABC):

    @abstractmethod
    def authenticate(self, user_id: str, password: str) -> Optional[User]:
        """Verify credentials. Returns User on success, None on failure."""

    @abstractmethod
    def authenticate_qr(self, qr_payload: str) -> Optional[User]:
        """Decode a QR payload and verify the embedded credentials."""

    @abstractmethod
    def record_failed_attempt(self, user_id: str) -> None:
        """Increment failed login counter — used for throttling."""

    @abstractmethod
    def is_locked_out(self, user_id: str) -> bool:
        """Returns True if the account is temporarily locked."""
```

`AuthenticationService` implements this against `CsvUserRepository` + bcrypt password check.
It owns the lockout counter (in-memory dict or persisted CSV column).

**Stub:** `StubAuthenticationService` — accepts any credentials, returns a fixed `User`.
Used in tests and standalone runners.

---

### Step 2 — `IAuthorizationService` + `AuthorizationService`

**New files:**
- `src/engine/auth/i_authorization_service.py`
- `src/engine/auth/authorization_service.py`

```python
class IAuthorizationService(ABC):

    @abstractmethod
    def get_visible_apps(self, role: Role, all_specs: List[ApplicationSpec]) -> List[ApplicationSpec]:
        """Filter specs to only those the given role may access."""

    @abstractmethod
    def can_access(self, role: Role, app_id: str) -> bool:
        """Single app check by stable app_id — used for runtime guards."""

    @abstractmethod
    def get_all_permissions(self) -> Dict[str, List[Role]]:
        """Full map keyed by app_id — used by the admin permissions editor UI."""

    @abstractmethod
    def set_permissions(self, app_id: str, roles: List[Role]) -> None:
        """Admin updates role access for an app_id. Persisted immediately."""
```

`AuthorizationService` implements this against `PermissionsRepository`.
Enforces the invariant: `UserManagement` always includes `Role.ADMIN`.

**Stub:** `StubAuthorizationService` — returns all specs visible, `can_access` always `True`.

---

### Step 3 — Add `app_id` to `ApplicationSpec`

**File:** `src/robot_systems/base_robot_system.py`

```python
@dataclass(frozen=True)
class ApplicationSpec:
    name: str           # display name, may change freely
    folder_id: int
    icon: str = "fa5s.cog"
    factory: Optional[Callable] = field(default=None, compare=False)
    app_id: str = ""    # stable snake_case key used in permissions.json — never change once set
```

`__post_init__` auto-derives `app_id` from `name` if not provided:
```python
def __post_init__(self):
    if not self.app_id:
        object.__setattr__(self, "app_id", self.name.lower().replace(" ", "_"))
```

All existing `ApplicationSpec(name="GlueDashboard", ...)` calls auto-derive `app_id="glue_dashboard"` — **no changes needed to `glue_robot_system.py`**.

### Step 4 — `PermissionsRepository`

**New file:** `src/robot_systems/glue/domain/permissions/permissions_repository.py`

```python
class PermissionsRepository:
    def __init__(self, file_path: str, known_app_ids: List[str]): ...

    def get_allowed_roles(self, app_id: str) -> List[Role]:
        """Returns roles for this app_id. Defaults to [Role.ADMIN] if not in file."""

    def set_allowed_roles(self, app_id: str, roles: List[Role]) -> None:
        """Serializes as Role.value strings. Persists immediately."""

    def get_all(self) -> Dict[str, List[Role]]:
        """Full mapping keyed by app_id — used by the admin permissions editor."""
```

Serialization rule: **always `Role.value` strings** — same convention as `User.to_dict()`.
Deserialization: `Role(value_string)` with fallback to `Role.ADMIN` on unknown value — same pattern as `User.from_dict()`.

On load, auto-migrates stale files: adds missing `app_id`s with `["Admin"]`, removes unknown keys.

### Step 2 — `UserSession` singleton

**New file:** `src/engine/system/user_session.py`

```python
class UserSession:
    """Thread-safe singleton holding the currently logged-in user."""

    @classmethod
    def get(cls) -> 'UserSession': ...

    def login(self, user: User) -> None: ...
    def logout(self) -> None: ...

    @property
    def current_user(self) -> Optional[User]: ...

    @property
    def current_role(self) -> Optional[Role]: ...
```

### Step 3 — `LoginWindow`

**New file:** `src/applications/login/login_window.py`

A `QDialog` subclass — shown from `main.py` before `AppShell` is built. Not registered in `GlueRobotSystem.shell`.

#### 3a — Setup Wizard step (first run / onboarding)

Before the login tabs appear, a `SetupStepsWidget` is shown full-width:
- Displays a machine/instruction image + translatable instructions text
- **NEXT** button → transitions to the login tabs
- Optional: poll for a physical hardware button press (`check_physical_button()` on 500ms `QTimer`)
- **First-run detection**: if `users.csv` is empty, replace the login tabs with a "Create first admin" wizard (collect name, ID, password → write to CSV → set session → proceed). No default credentials ever created.

#### 3b — Login tabs (two methods)

`QTabWidget` with two tabs, icon-driven (responsive icon sizing: 30–80px, ~8% of window width):

**Tab 0 — Username / Password**
- `FocusLineEdit` for User ID (numeric only, virtual keyboard support)
- `FocusLineEdit` for Password (masked echo, virtual keyboard support)
- `MaterialButton` → LOGIN
- Error feedback via `ToastWidget` (2-second display)
- Validation: both fields required, ID must be digits
- Error codes: empty fields / non-numeric ID / wrong password / user not found

**Tab 1 — QR Code**
- **Safety warning dialog** on tab switch: *"Robot will move to login position — ensure area is clear"* → OK / CANCEL
- On OK: calls `LoginApplicationService.move_to_login_pos()` (robot moves to QR scan position)
- On CANCEL: reverts silently to Tab 0
- Live `CameraFeed` widget (640×360, 30 fps)
- `QTimer` polls every 2000ms → `LoginApplicationService.try_qr_login()` → returns `(user_id, password)` or None
- On detection: emergency-stop scanning → authenticate → proceed
- Multiple race-condition guards: `qr_scanning_active` flag + timer-active check + emergency stop function
- On window close or tab switch away: `force_stop_scanning()` + restore contour detection

#### 3c — Window behaviour
- ESC key and window close button **disabled** (`_allow_close` flag, only set `True` after successful auth)
- Default tab (Normal or QR) configurable via `loginWindowConfig.json` (`DEFAULT_LOGIN: "NORMAL"` or `"QR"`)
- Layout: logo panel left (purple gradient, responsive scaling) + login panel right (`QStackedLayout`)
- On success: `UserSession.get().login(user)` → `dialog.accept()` → `main.py` proceeds

#### 3d — QR code generation (admin side — existing feature, just needs wiring)

`UserManagementApplicationService.generate_qr(record)` already generates a per-user QR image.
Wire a **"Generate QR"** button per user row in the `UserManagement` view that:
1. Calls `generate_qr(record)` → saves QR image to disk
2. Optionally calls `send_access_package(record, qr_path)` → emails it to the user

No new service code needed — only a UI button in `user_management_view.py`.

### Step 4 — Permissions editor in `UserManagement`

Extend the existing `UserManagement` application with a second tab: **"App Permissions"**.

The tab shows a table:

| App | Admin | Operator | Viewer |
|-----|-------|----------|--------|
| GlueDashboard | ✅ | ✅ | ✅ |
| WorkpieceEditor | ✅ | ✅ | ☐ |
| RobotSettings | ✅ | ☐ | ☐ |
| ... | | | |

Each checkbox calls `PermissionsRepository.set_allowed_roles(app_name, roles)`.
Changes take effect on next login.

**Files to modify:**
- `src/applications/user_management/view/user_management_view.py` — add tab
- `src/applications/user_management/service/i_user_management_service.py` — add `get_permissions()` / `set_permissions()` methods
- `src/applications/user_management/service/user_management_application_service.py` — implement
- `src/robot_systems/glue/application_wiring.py` — inject `PermissionsRepository` into service

### Step 5 — Filter specs at startup in `main.py`

**File:** `src/bootstrap/main.py`

Modified startup sequence:
```
1. EngineContext.build()
2. SystemBuilder ... .build(GlueRobotSystem)
3. ShellConfigurator.configure(GlueRobotSystem)
4. QApplication(sys.argv)
5. Show LoginWindow (blocking QDialog)
   ├─ SetupStepsWidget (onboarding / first-run wizard)
   ├─ Tab 0: Username + Password login
   └─ Tab 1: QR code auto-scan login (camera + robot positioning)
   → on success: UserSession.get().login(user)
6. Build AuthorizationService(PermissionsRepository(permissions_path))
7. visible_specs = authz_service.get_visible_apps(session.current_role, all_specs)
8. ApplicationLoader — load only visible specs
9. AppShell — receives pre-filtered descriptors
```

---

## Critical Files

| File | Change |
|------|--------|
| `src/engine/auth/i_authentication_service.py` | **New** — authentication interface |
| `src/engine/auth/authentication_service.py` | **New** — bcrypt credential check + lockout logic |
| `src/engine/auth/i_authorization_service.py` | **New** — authorization interface |
| `src/engine/auth/authorization_service.py` | **New** — role-based app filtering via `PermissionsRepository` |
| `src/engine/system/user_session.py` | **New** — thread-safe session singleton |
| `src/robot_systems/glue/domain/permissions/permissions_repository.py` | **New** — JSON-backed permissions store |
| `src/robot_systems/glue/storage/settings/permissions.json` | **New** — default permissions config |
| `src/bootstrap/main.py` | Show login first, filter specs via `IAuthorizationService` |
| `src/applications/login/login_window.py` | **New** — `QDialog` with setup wizard + dual-tab login (password + QR) |
| `src/applications/login/login_application_service.py` | **New** — wraps `IAuthenticationService`, adds `try_qr_login()` + `move_to_login_pos()` |
| `src/applications/user_management/` | Extend with "App Permissions" tab; inject `IAuthorizationService` |
| `src/robot_systems/glue/application_wiring.py` | Wire `AuthenticationService` + `AuthorizationService` with concrete dependencies |

**`ApplicationSpec` is NOT modified** — permissions are fully external to the code.

---

## Key Design Decisions

- **Admin-configurable at runtime**: no code changes needed to adjust who can see what — admin edits it via the UI.
- **Safe default**: any app not listed in `permissions.json` defaults to `["Admin"]` only.
- **Changes take effect on next login**: simplest approach; no need to rebuild `AppShell` at runtime.
- **No `pl_gui/` changes**: filtering happens before `AppShell`, which already handles empty folders.
- **Shared repository path**: `LoginWindow` and `UserManagement` share the same `_USERS_STORAGE` path — no duplication.

---

## Verification

1. Log in as ADMIN → open UserManagement → "App Permissions" tab → uncheck Operator from WorkpieceEditor → save
2. Log out, log in as OPERATOR → verify WorkpieceEditor is gone
3. Log in as ADMIN again → re-enable → log in as OPERATOR → verify it's back
4. Delete `permissions.json` → restart → verify all apps default to Admin-only
5. Run: `python tests/run_tests.py` — all existing tests pass unchanged

---

## Additional Good Practices

### 1 — Password hashing (security critical)
Passwords must never be stored in plain text in `users.csv`. Use `bcrypt` or `argon2-cffi` to hash on creation and verify on login. The `CsvUserRepository` should store only the hash; the `LoginWindow` compares via `bcrypt.checkpw()`.

### 2 — Inactivity timeout / auto-logout
For an industrial robot platform, an unattended logged-in session is a safety risk. Add a `QTimer` in the shell that resets on any mouse/keyboard event. On timeout: hide the shell, show the `LoginWindow` again, call `UserSession.logout()`. The `AppShell` is rebuilt after re-login with potentially different filtered specs.

### 3 — Audit log
Record every login, logout, and permission change to a `audit.log` file (append-only). Minimum fields: `timestamp | user_id | action | detail`. This is required in most industrial/compliance environments and is invaluable for debugging access issues.

```
2026-03-16 09:14:22 | user_id=3  | LOGIN        | role=Operator
2026-03-16 09:45:01 | user_id=1  | PERM_CHANGE  | app=WorkpieceEditor roles=[Admin,Operator]
2026-03-16 10:02:15 | user_id=3  | LOGOUT       | reason=timeout
```

### 4 — Login attempt throttling
After N consecutive failed logins (e.g. 5), lock the account for M minutes. Track failed attempts in memory (or persist to CSV). The `UserManagementApplicationService` should expose `reset_lockout(user_id)` for the admin.

### 5 — Bootstrap admin account (first-run wizard, no default credentials)
On first run, if `users.csv` is empty, skip the login tabs entirely and show a **"Create first admin" wizard** instead:
1. Prompt: First Name, Last Name, numeric ID, Password, Confirm Password
2. Validate: passwords match, ID not already taken (can't be — file is empty), all fields filled
3. Create the user with `Role.ADMIN` and write to `users.csv`
4. Proceed directly to the shell (no need to log in again — session is set immediately)

**No default `admin/admin` is ever created.** A known default credential is a security liability — every industrial deployment would need to remember to change it.

### 6 — Admin is always protected
`UserManagement` and the `Admin` role itself must never be removable from `permissions.json` via the UI — enforce this in `PermissionsRepository.set_allowed_roles()`:

```python
if app_id == "user_management":
    roles = list(set(roles) | {Role.ADMIN})  # Admin can never lose access
```

### 7 — Logout button in shell
The shell header/toolbar should have a logout button visible to all users. On click: `UserSession.logout()` → hide `AppShell` → show `LoginWindow` → rebuild with new role's filtered specs. Since `pl_gui/` is read-only, this button can live in a thin wrapper widget created in `main.py` that wraps `AppShell`.

### 8 — New apps default to Admin-only
When a new `ApplicationSpec` is added to `GlueRobotSystem.shell` but has no entry in `permissions.json`, `PermissionsRepository.get_allowed_roles()` returns `[Role.ADMIN]`. This means new features are invisible to other roles until the admin explicitly grants access — a secure default.

### 9 — Permissions schema versioning
If a new app is added or an app is renamed, old `permissions.json` files will have stale keys. On load, `PermissionsRepository` should:
1. Add missing apps with default `["Admin"]`
2. Remove keys for apps that no longer exist in `GlueRobotSystem.shell`
3. Save the migrated file back

This keeps the JSON in sync with the codebase automatically.

### 10 — Separate login service from user management service
`LoginApplicationService` and `UserManagementApplicationService` share the same `CsvUserRepository` but have different responsibilities. Keep them as two separate services — don't merge them. Login only needs `authenticate(username, password) -> Optional[User]`; user management needs full CRUD. This keeps the login path minimal and easy to audit.
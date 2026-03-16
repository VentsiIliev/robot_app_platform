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
| First-run bootstrap | **"Create first admin" wizard — no default credentials** | A default `admin/admin` is a known attack vector; forcing the operator to set their own password on first boot is safer |
| Role serialization | **`Role.value` strings** (`"Admin"`, `"Operator"`, `"Viewer"`) everywhere | Consistent with the existing `User.to_dict()` / `User.from_dict()` pattern already in the codebase |
| Permission keys | **`app_id: str` on `ApplicationSpec`** (stable snake_case, camelCase→snake auto-derived) | Decouples display `name` from storage key — renaming a display name won't silently break `permissions.json` |

---

## Architecture Overview

```
LoginWindow (QDialog)
       │ credentials / QR scan
       ↓
IAuthenticationService          ← "who are you?"  (src/engine/auth/)
  └─ AuthenticationService      ← bcrypt + lockout (internal, not on interface)
       │ returns Optional[User]
       ↓
UserSession (singleton)         ← holds current User + Role  (src/engine/system/)
       │
       ↓
IAuthorizationService           ← "what can you do?"  (src/engine/auth/)
  └─ AuthorizationService       ← queries IPermissionsRepository
       │ uses
       ↓
IPermissionsRepository          ← interface in engine; impl in glue domain
  └─ PermissionsRepository      ← JSON-backed, maps app_id → [Role.value strings]
       │
       ↓
main.py                         ← visible_specs = authz.get_visible_apps(role, all_specs)
       ↓
AppShell                        ← receives pre-filtered descriptors (no changes needed)
```

**Authentication** — *"Are these credentials valid? Who is this user?"*
**Authorization** — *"Given this user's role, which apps are they allowed to see?"*
Kept as separate interfaces with separate responsibilities.

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
@dataclass(frozen=True)
class ApplicationSpec:
    name: str           # display name — may change freely
    folder_id: int
    icon: str = "fa5s.cog"
    factory: Optional[Callable] = field(default=None, compare=False)
    app_id: str = ""    # stable key for permissions.json — never change once set

    def __post_init__(self):
        if not self.app_id:
            # CamelCase → snake_case: "GlueDashboard" → "glue_dashboard"
            import re
            snake = re.sub(r'(?<!^)(?=[A-Z])', '_', self.name).lower()
            object.__setattr__(self, "app_id", snake)
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
        """Verify credentials. Returns User on success, None on failure.
        Internally handles lockout — callers do not need to know about it."""

    @abstractmethod
    def authenticate_qr(self, qr_payload: str) -> Optional[User]:
        """Decode QR payload → extract user_id + password → call authenticate()."""
```

Throttling (failed attempt counter, lockout timer) lives **inside** `AuthenticationService`,
not on the interface. Callers just get `None` back — they don't need to know why.

**Stub:** `StubAuthenticationService` — accepts any credentials, returns a fixed `User`.

---

### Step 3 — `IPermissionsRepository` + `PermissionsRepository`

**New files:**
- `src/engine/auth/i_permissions_repository.py` — interface (engine layer, no glue imports)
- `src/robot_systems/glue/domain/permissions/permissions_repository.py` — JSON-backed implementation

```python
class IPermissionsRepository(ABC):

    @abstractmethod
    def get_allowed_roles(self, app_id: str) -> List[Role]:
        """Returns allowed roles. Defaults to [Role.ADMIN] if app_id not found."""

    @abstractmethod
    def set_allowed_roles(self, app_id: str, roles: List[Role]) -> None:
        """Persist immediately. Serializes as Role.value strings."""

    @abstractmethod
    def get_all(self) -> Dict[str, List[Role]]:
        """Full map keyed by app_id — used by the admin permissions editor."""
```

`PermissionsRepository` serializes/deserializes using `Role.value` strings — same pattern as
`User.to_dict()` / `User.from_dict()`. Unknown value strings fall back to `Role.ADMIN`.

On load, auto-migrates the file: adds missing `app_id`s with `["Admin"]`, removes keys
that no longer exist in the known app list. Saves the migrated file back.

---

### Step 4 — `IAuthorizationService` + `AuthorizationService`

**New files:** `src/engine/auth/i_authorization_service.py`, `authorization_service.py`

```python
class IAuthorizationService(ABC):

    @abstractmethod
    def get_visible_apps(self, role: Role, all_specs: List[ApplicationSpec]) -> List[ApplicationSpec]:
        """Filter specs to only those accessible by this role."""

    @abstractmethod
    def can_access(self, role: Role, app_id: str) -> bool:
        """Point check — for runtime guards inside apps."""
```

Read-only. Admin editing of permissions goes through `IUserManagementService` (Step 6),
not through this interface.

`AuthorizationService` enforces one invariant: `user_management` always includes `Role.ADMIN`
(checked inside `AuthorizationService`, not the repository).

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
Uses `IAuthenticationService` via a thin `LoginApplicationService`.

#### 6a — First-run: "Create first admin" wizard

If `users.csv` is empty, show the wizard instead of the login tabs:
1. Fields: First Name, Last Name, numeric ID, Password, Confirm Password
2. Validate: all filled, passwords match
3. Hash password → write user with `Role.ADMIN` to CSV
4. Set `UserSession` immediately → skip the login screen → proceed to shell

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
  → OK calls `LoginApplicationService.move_to_login_pos()` / CANCEL reverts to Tab 0
- Live `CameraFeed` (640×360, 30 fps)
- `QTimer` polls every 2000 ms → `LoginApplicationService.try_qr_login()` → `Optional[User]`
- On detection: emergency-stop scanning (race-condition guards: flag + timer-active check)
  → `UserSession.login(user)` → `dialog.accept()`
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

Add a second tab to the existing `UserManagement` application:

| App | Admin | Operator | Viewer |
|-----|-------|----------|--------|
| GlueDashboard | ✅ | ✅ | ✅ |
| WorkpieceEditor | ✅ | ✅ | ☐ |
| RobotSettings | ✅ | ☐ | ☐ |

Each checkbox calls `IUserManagementService.set_permissions(app_id, roles)`.
Changes take effect on next login.

`IUserManagementService` gains two methods:
- `get_permissions() -> Dict[str, List[Role]]`
- `set_permissions(app_id: str, roles: List[Role]) -> None`

`UserManagementApplicationService` delegates to `IPermissionsRepository`.

**Files:**
- `src/applications/user_management/service/i_user_management_service.py` — add two methods
- `src/applications/user_management/service/user_management_application_service.py` — implement
- `src/applications/user_management/view/user_management_view.py` — add tab
- `src/robot_systems/glue/application_wiring.py` — inject `PermissionsRepository` into service

---

### Step 8 — Wire everything in `main.py`

```
1. EngineContext.build()
2. SystemBuilder ... .build(GlueRobotSystem)
3. ShellConfigurator.configure(GlueRobotSystem)
4. QApplication(sys.argv)
5. Show LoginWindow (blocking QDialog)
   ├─ First run?  → "Create first admin" wizard → set UserSession → skip to 7
   ├─ SetupStepsWidget (onboarding) → NEXT
   ├─ Tab 0: Username + Password
   └─ Tab 1: QR auto-scan (camera + robot positioning)
   → on success: UserSession.get().login(user)
6. authz = AuthorizationService(PermissionsRepository(permissions_path, known_app_ids))
7. visible_specs = authz.get_visible_apps(session.current_role, GlueRobotSystem.shell.applications)
8. ApplicationLoader — load only visible_specs
9. AppShell — receives pre-filtered descriptors
```

---

## Critical Files

| File | Change |
|------|--------|
| `src/robot_systems/base_robot_system.py` | Add `app_id` field + camelCase→snake derivation to `ApplicationSpec` |
| `src/engine/auth/i_authentication_service.py` | **New** — `authenticate()`, `authenticate_qr()` |
| `src/engine/auth/authentication_service.py` | **New** — bcrypt check; lockout internal |
| `src/engine/auth/i_permissions_repository.py` | **New** — repository interface (engine layer) |
| `src/engine/auth/i_authorization_service.py` | **New** — `get_visible_apps()`, `can_access()` |
| `src/engine/auth/authorization_service.py` | **New** — queries `IPermissionsRepository` |
| `src/engine/system/user_session.py` | **New** — thread-safe session singleton |
| `src/robot_systems/glue/domain/permissions/permissions_repository.py` | **New** — JSON impl of `IPermissionsRepository` |
| `src/robot_systems/glue/storage/settings/permissions.json` | **New** — default permissions |
| `src/bootstrap/main.py` | Show login first; filter via `IAuthorizationService` |
| `src/applications/login/login_window.py` | **New** — `QDialog`: wizard + dual-tab login |
| `src/applications/login/login_application_service.py` | **New** — wraps `IAuthenticationService`; adds `try_qr_login()`, `move_to_login_pos()` |
| `src/applications/user_management/` | Add "App Permissions" tab; inject `IPermissionsRepository` |
| `src/robot_systems/glue/application_wiring.py` | Wire all new services with concrete deps |

---

## Key Design Decisions

- **AuthN/AuthZ separation**: two focused interfaces, each with minimal surface area.
- **Throttling is internal**: `IAuthenticationService.authenticate()` returns `None` for locked accounts — callers don't need to know the reason.
- **AuthZ is read-only**: `IAuthorizationService` only answers questions. Admin permission editing goes through `IUserManagementService`.
- **Layer integrity**: `IPermissionsRepository` interface lives in `src/engine/auth/` so `AuthorizationService` (engine) never imports from `src/robot_systems/` (glue).
- **No `pl_gui/` changes**: filtering happens before `AppShell`.
- **Changes take effect on next login**: no need to rebuild `AppShell` at runtime.
- **Safe defaults**: unknown `app_id` → `[Role.ADMIN]`; unknown role string → `Role.ADMIN`.

---

## Good Practices

### 1 — Password hashing
Store only bcrypt hashes in `users.csv`. `AuthenticationService` hashes on creation and verifies
with `bcrypt.checkpw()` on login. `CsvUserRepository` never sees plain text.

### 2 — Inactivity timeout / auto-logout
Add a `QTimer` in the shell wrapper (in `main.py`, not `pl_gui/`) that resets on any
mouse/keyboard event. On timeout: `UserSession.logout()` → hide shell → show `LoginWindow`
→ rebuild `AppShell` with new role's filtered specs.

### 3 — Audit log
Append-only `audit.log` for every login, logout, and permission change:
```
2026-03-16 09:14:22 | user_id=3 | LOGIN       | role=Operator
2026-03-16 09:45:01 | user_id=1 | PERM_CHANGE | app=workpiece_editor roles=[Admin,Operator]
2026-03-16 10:02:15 | user_id=3 | LOGOUT      | reason=timeout
```

### 4 — Login throttling
After N failed attempts, `AuthenticationService` locks the account internally for M minutes.
`UserManagementApplicationService` exposes `reset_lockout(user_id)` for the admin.

### 5 — Admin is always protected
`AuthorizationService` enforces: `user_management` always includes `Role.ADMIN`, regardless
of what `IPermissionsRepository` returns. One guard in one place.

### 6 — Logout button
Lives in a thin wrapper widget created in `main.py` that wraps `AppShell` (since `pl_gui/`
is read-only). On click: `UserSession.logout()` → re-show `LoginWindow` → rebuild shell.

---

## Verification

1. Fresh install (no `users.csv`) → wizard appears → create admin → shell opens with all apps
2. Admin unchecks Operator from WorkpieceEditor → log in as Operator → app is gone
3. Re-enable → log in as Operator → app is back
4. Delete `permissions.json` → restart → all apps default to Admin-only
5. Wrong password 5× → account locked → correct password returns same error until timeout
6. Run: `python tests/run_tests.py` — all existing tests pass unchanged
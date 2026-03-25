# `src/engine/auth/` — Authentication, Authorization & Session

The `auth` package provides role-based access control for the robot platform. It is composed of narrow, composable interfaces so that each layer of the application only receives the access it needs.

---

## Package Structure

```
auth/
├── i_authenticated_user.py       ← IAuthenticatedUser ABC
├── authenticated_user.py         ← AuthenticatedUser (concrete)
├── auth_user_record.py           ← AuthUserRecord (data transfer object)
├── i_auth_user_repository.py     ← IAuthUserRepository ABC
├── i_authentication_service.py   ← IAuthenticationService ABC
├── authentication_service.py     ← AuthenticationService (concrete)
├── i_authorization_service.py    ← IAuthorizationService ABC (read-only)
├── i_permissions_admin_service.py← IPermissionsAdminService ABC (read + write)
├── authorization_service.py      ← AuthorizationService (concrete, implements both)
├── i_permissions_repository.py   ← IPermissionsRepository ABC
├── json_permissions_repository.py← JsonPermissionsRepository (JSON-backed)
├── i_session_service.py          ← ISessionService ABC
├── user_session.py               ← UserSession (thread-safe concrete)
└── permissions_migrator.py       ← ensure_permissions_current() utility
```

---

## Interface Hierarchy

```
IAuthenticatedUser
  └── AuthenticatedUser(IAuthenticatedUser)
        └── wraps AuthUserRecord

IAuthenticationService
  └── AuthenticationService
        └── depends on IAuthUserRepository

IAuthorizationService  (read-only — used by runtime guards and main.py)
  └── IPermissionsAdminService  (extends with write ops — used only by permissions editor)
        └── AuthorizationService
              └── depends on IPermissionsRepository

ISessionService
  └── UserSession (thread-safe)

IPermissionsRepository
  └── JsonPermissionsRepository
```

---

## Core Interfaces

### `IAuthenticatedUser`

```python
class IAuthenticatedUser(ABC):
    @property
    def user_id(self) -> str: ...   # stable identifier
    @property
    def role(self) -> Enum: ...     # compared via .value — no concrete Role type assumed
```

`role` is an `Enum` — comparisons are always done on `.value` strings so this interface works across robot systems with different role enums.

---

### `IAuthenticationService`

```python
class IAuthenticationService(ABC):
    def authenticate(self, user_id: str, password: str) -> Optional[IAuthenticatedUser]: ...
    def authenticate_qr(self, qr_payload: str) -> Optional[IAuthenticatedUser]: ...
```

Returns `None` on failure. Lockout tracking (if any) is an internal implementation detail — not part of the interface.

**QR payload format:** `"user_id:password"` — decoded by splitting on the first `:`.

---

### `IAuthorizationService`

```python
class IAuthorizationService(ABC):
    def get_visible_apps(self, user: IAuthenticatedUser, all_specs: list) -> list: ...
    def can_access(self, user: IAuthenticatedUser, app_id: str) -> bool: ...
```

Read-only. Used by `main.py` and any runtime navigation guard. Must NOT be used by the permissions editor — use `IPermissionsAdminService` there instead.

---

### `IPermissionsAdminService`

```python
class IPermissionsAdminService(IAuthorizationService):
    def get_all_permissions(self) -> dict[str, list[str]]: ...
    def set_permissions(self, app_id: str, role_values: list[str]) -> None: ...
```

Extends `IAuthorizationService` with write operations for the permissions editor UI. Implementations may enforce role invariants (e.g., an admin role cannot be removed from a protected app).

---

### `ISessionService`

```python
class ISessionService(ABC):
    def login(self, user: IAuthenticatedUser) -> None: ...
    def logout(self) -> None: ...                              # safe when already logged out
    @property
    def current_user(self) -> Optional[IAuthenticatedUser]: ...
    @property
    def current_role(self) -> Optional[Enum]: ...
    def is_authenticated(self) -> bool: ...
```

---

## Concrete Implementations

### `AuthenticationService`

Backed by `IAuthUserRepository`. `authenticate_qr()` decodes `"user_id:password"` then calls `authenticate()`. No external dependencies beyond the repository.

```python
service = AuthenticationService(repository=my_repo)
user = service.authenticate("alice", "secret")   # IAuthenticatedUser | None
```

### `AuthorizationService`

Backed by `IPermissionsRepository`. Implements both `IAuthorizationService` and `IPermissionsAdminService`. Role comparison is done on `str(role.value)` — no concrete role type is imported.

```python
service = AuthorizationService(
    repository=my_permissions_repo,
    protected_app_role_values={"admin_panel": ["Admin"]},  # roles that can never be removed
)
```

`protected_app_role_values` ensures that certain roles always retain access to specific apps even after a `set_permissions()` call.

### `UserSession`

Thread-safe session holder. Instantiated once in `main.py` and injected everywhere as `ISessionService`.

```python
session = UserSession()
session.login(authenticated_user)
session.is_authenticated()   # True
session.current_role         # the user's role Enum value
session.logout()
```

### `JsonPermissionsRepository`

Reads and writes a JSON file at the given path. Auto-creates parent directories and an empty file if missing.

```python
repo = JsonPermissionsRepository(
    file_path="storage/settings/glue/permissions.json",
    default_role_values=["Admin"],   # used when app_id not in file
)
```

**File format:**
```json
{
  "glue_dispenser": ["Admin", "Operator"],
  "work_area_settings": ["Admin"]
}
```

Keys are `app_id` strings; values are lists of role value strings.

---

## Data Model

### `AuthUserRecord`

```python
@dataclass(frozen=True)
class AuthUserRecord:
    user_id:  str
    password: str
    role:     Enum
    payload:  dict[str, Any]   # extra robot-system-specific fields
```

Intentionally narrow so authentication can be reused across robot systems regardless of underlying user storage. `IAuthUserRepository.get_by_id()` returns this.

---

## Permissions Migration

**File:** `permissions_migrator.py`

```python
def ensure_permissions_current(
    repo:                IPermissionsRepository,
    known_app_ids:       list[str],
    default_role_values: list[str],
) -> None: ...
```

Adds any `app_id` not already present in the repository with the provided defaults. Call this during startup after building the permissions repository and before the shell renders navigation — it ensures newly added apps get sensible defaults without overwriting existing custom permissions.

```python
ensure_permissions_current(
    repo=permissions_repo,
    known_app_ids=[spec.app_id for spec in robot_system.shell.applications],
    default_role_values=["Admin"],
)
```

---

## Wiring Example

```python
# In robot system bootstrap
user_repo        = GlueUserRepository(...)          # robot-system specific
permissions_repo = JsonPermissionsRepository(path, default_role_values=["Admin"])

ensure_permissions_current(permissions_repo, known_app_ids, default_role_values=["Admin"])

auth_service  = AuthenticationService(user_repo)
authz_service = AuthorizationService(permissions_repo, protected_app_role_values={...})
session       = UserSession()
```

---

## Interface Assignment per Layer

| Consumer | Use this interface |
|----------|--------------------|
| Login controller | `IAuthenticationService` |
| Navigation / app launcher | `IAuthorizationService` |
| Permissions editor model | `IPermissionsAdminService` |
| Any screen checking login state | `ISessionService` |
| Internal auth implementations | `IAuthUserRepository`, `IPermissionsRepository` |

---

## Design Notes

- **Role-value comparison** — `AuthorizationService` uses `str(getattr(role, "value", role))`. This means the concrete `Role` enum is never imported by the engine; robot systems can define their own role enumerations.
- **`IAuthorizationService` is read-only by design** — only the narrow write interface (`IPermissionsAdminService`) is exposed where needed, following the principle of least privilege.
- **Never access `UserSession` via a global** — always inject `ISessionService` so components remain testable.
- **`protect_app_role_values`** — when set, `set_permissions()` merges the protected roles back in after any update, preventing accidental lockout of admin roles.

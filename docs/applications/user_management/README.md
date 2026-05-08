# `src/applications/user_management/` — User Management

Schema-driven CRUD screen for managing user accounts. The data schema (fields, types, labels) is declared by the robot system — the application itself is generic and schema-agnostic. Backed by a CSV repository.

---

## MVC Structure

```
user_management/
├── service/
│   ├── i_user_management_service.py              ← IUserManagementService (7 methods)
│   ├── stub_user_management_service.py           ← In-memory stub with 3 hardcoded users
│   └── user_management_application_service.py   ← Delegates to IUserRepository
├── domain/
│   ├── user_schema.py                            ← UserSchema, UserRecord, FieldDescriptor
│   ├── i_user_repository.py                      ← IUserRepository ABC
│   ├── csv_user_repository.py                    ← CSV-backed implementation
│   ├── auth_user_repository_adapter.py           ← Adapts IUserRepository to engine auth
│   ├── default_schema.py                         ← Minimal default schema
│   └── user.py
├── model/
│   └── user_management_model.py
├── view/
│   └── user_management_view.py
├── controller/
│   └── user_management_controller.py
└── user_management_factory.py
```

---

## `IUserManagementService`

```python
class IUserManagementService(ABC):
    def get_schema(self)                                        -> UserSchema: ...
    def get_all_users(self)                                     -> List[UserRecord]: ...
    def add_user(self, record: UserRecord)                      -> tuple[bool, str]: ...
    def update_user(self, record: UserRecord)                   -> tuple[bool, str]: ...
    def delete_user(self, user_id)                              -> tuple[bool, str]: ...
    def generate_qr(self, record: UserRecord)                   -> tuple[bool, str, Optional[str]]: ...
    def send_access_package(self, record: UserRecord, qr_path)  -> tuple[bool, str]: ...
```

`generate_qr` returns `(success, message, qr_image_path)`.

---

## Domain Model

### `UserSchema`

Declares the fields for a user record. Constructed by the robot system and passed to the factory.

```python
@dataclass
class FieldDescriptor:
    key:               str
    label:             str
    widget:            str          # "text" | "password" | "combo" | "email" | "int"
    required:          bool = True
    table_display:     bool = True
    read_only_on_edit: bool = False
    options:           Optional[List[str]] = None
    mask_in_table:     bool = False  # shows "****" in the table (e.g. PIN)

@dataclass
class UserSchema:
    fields:  List[FieldDescriptor]
    id_key:  str = "id"             # primary key field name
```

### `UserRecord`

A schema-agnostic wrapper around a `dict`. Used for all read/write operations — no hard-coded field names in application code.

### `CsvUserRepository`

Persists `UserRecord` objects to a CSV file at a configurable path. Schema is provided at construction time to determine column order and the ID field.

### `AuthUserRepositoryAdapter`

Bridges the richer user-management repository contract to the thin engine auth contract.

- input: `IUserRepository`
- output: `IAuthUserRepository`
- maps a `UserRecord` into `AuthUserRecord`

This keeps the login/authentication path reusable without forcing the CRUD-oriented user-management stack into `src/engine/`.

---

## Glue System Schema

The glue robot system now declares its role and permission policy on [glue_robot_system.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/glue_robot_system.py) via `role_policy`. The user schema itself is built from that declaration by [glue_user_schema.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/domain/users/glue_user_schema.py). The `UserManagement` application is still wired without knowing what fields or roles the glue system chose.

---

## Wiring in `GlueRobotSystem`

```python
role_policy = robot_system.__class__.role_policy
service = UserManagementApplicationService(
    CsvUserRepository(
        robot_system.users_storage_path(),
        build_glue_user_schema(role_policy.role_values),
    )
)
return WidgetApplication(widget_factory=lambda _ms: UserManagementFactory().build(service))
```

`ApplicationSpec`: `folder_id=3` (Administration), icon `fa5s.users-cog`.

---

## Localization

Both `UserManagementView` and `PermissionsView` use `QCoreApplication.translate("UserManagement", ...)` (exposed as `_t()`).

### Users table headers

Column headers come from `FieldDescriptor.label` (e.g. `"ID"`, `"First Name"`, …). They are set once at widget construction via `make_table(schema.get_table_headers())` and refreshed in `retranslateUi()`:

```python
def retranslateUi(self, *_) -> None:
    ...
    self._table.setHorizontalHeaderLabels(
        [self._t(h) for h in self._schema.get_table_headers()]
    )
```

`changeEvent` calls `retranslateUi()` on `QEvent.Type.LanguageChange`, so headers update immediately when the language is switched.

### Permissions table headers

Column headers come from the robot system's configured role values. For the glue system those are:

- `"Admin"`
- `"Operator"`
- `"Viewer"`
- `"Developer"`

They are translated inline inside `set_permissions()`:

```python
self._table.setHorizontalHeaderLabels([self._t(r) for r in role_values])
```

Because `PermissionsController._refresh()` repopulates the table, the role-value headers update whenever the table is refreshed. `PermissionsView` also has its own `changeEvent` retranslation hook for widget-owned static text.

### Translation catalog keys (context `"UserManagement"`)

Field labels and role values must exist as keys in the active catalog set. Shared keys can now live in:

- `src/applications/localization/*.json`
- optionally overridden by `src/robot_systems/<system>/storage/translations/*.json`

`UserManagement` is currently shared through `src/applications/localization/en.json` and `bg.json`. The glue system may still override or extend those entries in its own catalogs.

Current shared keys include:

```
"ID", "First Name", "Last Name", "Password", "Role", "Email"
"Admin", "Operator", "Viewer", "Developer"
```

---

## Design Notes

- **No robot/vision dependency**: `UserManagement` is wired without calling `get_service()` or `get_optional_service()`. It is purely settings + persistence.
- **Schema injection**: the view builds its form dynamically from `UserSchema.fields`, so adding a new field requires only a schema change — no view code changes. The same field `label` is used as both the table column header and the translation key, so keep labels stable once translated.
- **Regression coverage exists for runtime language changes**: the test suite now covers the real selector-to-embedded-view path, so a future break in `LanguageChange` propagation or shared catalog coverage should fail tests.
- **CSV persistence**: straightforward for operator-level access management; not intended for high-security production use.
- **Auth is now a thin adapter**: login/authentication no longer depends directly on `IUserRepository`. Instead, `AuthUserRepositoryAdapter` exposes only the minimal auth-facing data needed by the shared engine `AuthenticationService`.
- **Roles are robot-system-defined**: the permissions tab and first-admin creation no longer rely on a fixed shared `Role` enum. The robot system supplies the available role values, the default permission role values, and any protected app-role invariants.

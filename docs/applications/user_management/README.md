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

---

## Glue System Schema

The glue robot system defines its own `GLUE_USER_SCHEMA` in `src/robot_systems/glue/domain/users/`. The `UserManagement` application is wired with this schema without knowing what fields it contains.

---

## Wiring in `GlueRobotSystem`

```python
service = UserManagementApplicationService(
    CsvUserRepository(_USERS_STORAGE, GLUE_USER_SCHEMA)
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

Column headers are the `Role` enum values (`"Admin"`, `"Operator"`, `"Viewer"`, `"Developer"`). They are translated inline inside `set_permissions()`:

```python
self._table.setHorizontalHeaderLabels([self._t(r) for r in role_values])
```

Because `PermissionsController._refresh()` calls `set_permissions()` on every language-change event (via broker subscription), no additional `changeEvent` hook is needed in `PermissionsView`.

### Translation catalog keys (context `"UserManagement"`)

Field labels and role values must exist as keys in every catalog under
`src/robot_systems/<system>/storage/translations/`. The glue system catalogs (`en.json`, `bg.json`) include:

```
"ID", "First Name", "Last Name", "Password", "Role", "Email"
"Admin", "Operator", "Viewer", "Developer"
```

---

## Design Notes

- **No robot/vision dependency**: `UserManagement` is wired without calling `get_service()` or `get_optional_service()`. It is purely settings + persistence.
- **Schema injection**: the view builds its form dynamically from `UserSchema.fields`, so adding a new field requires only a schema change — no view code changes. The same field `label` is used as both the table column header and the translation key — keep them consistent.
- **CSV persistence**: straightforward for operator-level access management; not intended for high-security production use.

# `src/applications/login/` — Login

Modal dialog that gates access to the platform. On first run it creates the initial admin account; on subsequent runs it authenticates via username/password or QR code. ESC and the window close button are disabled — the dialog cannot be dismissed without a successful login.

---

## MVC Structure

```
login/
├── i_login_application_service.py  ← ILoginApplicationService (6 methods)
├── login_application_service.py    ← Concrete service
├── stub_login_application_service.py
├── i_qr_scanner.py                 ← IQrScanner ABC
├── login_factory.py                ← LoginFactory (static build, not ApplicationFactory)
├── model/
│   └── login_model.py              ← LoginModel (delegation + input validation)
├── view/
│   └── login_view.py               ← LoginView(QDialog) — 3-page stacked widget
├── controller/
│   └── login_controller.py         ← LoginController — navigation + auth + QR polling
└── example_usage.py
```

---

## `ILoginApplicationService`

```python
class ILoginApplicationService(ABC):
    def authenticate(self, user_id: str, password: str) -> Optional[IAuthenticatedUser]: ...
    def authenticate_qr(self, qr_payload: str) -> Optional[IAuthenticatedUser]: ...
    def try_qr_login(self) -> Optional[Tuple[str, str]]:
        """Poll camera for QR code. Returns (user_id, password) or None."""
    def move_to_login_pos(self) -> None:
        """Move robot to QR-scan position. No-op if no robot configured."""
    def is_first_run(self) -> bool:
        """True if user store is empty — setup wizard shown."""
    def create_first_admin(self, user_id, first_name, last_name, password) -> Tuple[bool, str]: ...
```

---

## `IQrScanner`

```python
class IQrScanner(ABC):
    def scan(self) -> Optional[str]:
        """Decode one QR code from the latest camera frame, or None."""
```

Injected into the concrete `LoginApplicationService`. Decouples camera/QR decoding from the service layer so different scanner implementations can be swapped.

---

## `LoginView`

`LoginView(QDialog)` — three-page stacked widget inside a two-panel layout (logo left, content right).

### Pages

| Page index | Name | Shown when |
|------------|------|------------|
| 0 | Setup | Dialog opens |
| 1 | First-run | `is_first_run()` returns True after setup confirmed |
| 2 | Login (tabs) | Normal flow after setup |

### Login tabs

| Tab | Content |
|-----|---------|
| Login | User ID + password fields; Enter key submits |
| QR Login | Live camera feed; QTimer polls every 2 s via `qr_scan_requested` signal |

### Key view signals

```python
setup_confirmed       = pyqtSignal()
login_submitted       = pyqtSignal(str, str)       # user_id, password
qr_scan_requested     = pyqtSignal()               # from QTimer, every 2 s
qr_tab_activated      = pyqtSignal()               # after safety confirmation
first_admin_submitted = pyqtSignal(str, str, str, str)  # id, first, last, password
```

### Key view setters

```python
def show_setup(self) -> None: ...
def show_login(self) -> None: ...
def show_first_run(self) -> None: ...
def show_error(self, message: str) -> None: ...
def accept_login(self, user: IAuthenticatedUser) -> None: ...   # closes dialog
def result_user(self) -> Optional[IAuthenticatedUser]: ...
def start_qr_scanning(self) -> None: ...   # starts QTimer
def stop_qr_scanning(self) -> None: ...
def update_camera_frame(self, frame) -> None: ...  # BGR numpy array
```

---

## `LoginController`

### Navigation flow

```
Dialog opens → show_setup()
  ↓ setup_confirmed
  ├─ is_first_run() == True  → show_first_run()
  └─ is_first_run() == False → show_login()

first_admin_submitted → create_first_admin() → authenticate() → accept_login()
login_submitted       → validate_login_input() → authenticate() → accept_login()
qr_tab_activated      → move_to_login_pos() (robot moves)
qr_scan_requested     → try_qr_login() → authenticate() → accept_login()
```

### Camera feed

Subscribes to `VisionTopics.LATEST_IMAGE` on the broker. Frames arrive on a hardware thread and are relayed to the Qt thread via `_Bridge(QObject)` with `pyqtSignal(object)`. When QR tab is not active, frames are still received but no QR decoding is attempted.

### Input validation (`LoginModel`)

- `user_id` must be non-empty and numeric (platform convention: integer IDs)
- `password` must be non-empty
- Errors are displayed inline via `show_error()`

---

## `LoginFactory`

Not an `ApplicationFactory` subclass — returns a `QDialog`, not an `IApplicationView`.

```python
view = LoginFactory.build(
    service=login_service,
    messaging=messaging_service,  # optional, for camera feed
    parent=None,
)
if view.exec() == QDialog.DialogCode.Accepted:
    user = view.result_user()
```

The factory assigns `view._controller = ctrl` to keep the controller alive while the dialog is open (same pattern as `ApplicationFactory`).

---

## Design Notes

- **ESC and close blocked** — `keyPressEvent` ignores `Key_Escape`; `closeEvent` ignores close unless `_allow_close` is set by `accept_login()`. This ensures no user can skip the login screen.
- **Setup page** — A "Simulate Blue Button" button stands in for a physical hardware trigger (TODO comment in source). This page is intended to wait for a hardware confirmation before allowing login.
- **QR safety warning** — Switching to the QR tab shows a `QMessageBox.warning` because the robot moves to the scan position. If the operator cancels, the tab reverts to Login.
- **First-run flow** — If `is_first_run()` is True, the first-admin creation form is shown instead of the normal login. After a successful admin creation the dialog immediately logs in with the new credentials.
- **Localization** — `LoginView` implements `retranslateUi()` and `changeEvent(LanguageChange)`. Translated via `QCoreApplication.translate("Login", text)` with source-text fallback.

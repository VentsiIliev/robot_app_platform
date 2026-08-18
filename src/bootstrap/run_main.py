from setproctitle import setproctitle

setproctitle("robot_app_platform")
# then continue with normal imports / startup
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PyQt6.QtCore import QObject, QEvent, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QWidget

from src.bootstrap.logging_config import setup_logging
from src.bootstrap.build_engine import EngineContext
from src.bootstrap.application_loader import ApplicationLoader
from src.bootstrap.shell_configurator import ShellConfigurator
from src.applications.base.notification_presenter import UserNotificationPresenter
from src.applications.base.robot_connection_notifier import RobotConnectionNotifier
from src.applications.base.widgets.startup_splash_view import StartupSplashView
from src.engine.localization.localization_service import LocalizationService
from src.shared_contracts.events.robot_events import RobotTopics
from src.robot_systems.system_builder import SystemBuilder
from src.bootstrap.startup_config import load_bootstrap_provider, load_startup_config
from src.bootstrap.ros_backend_launcher import build_ros_backend_launcher_from_env
from pl_gui.shell.AppShell import AppShell

_LOGGER = logging.getLogger("main")

#
# def _pin_process_to_non_rt_cores() -> None:
#     rt_cores = {14, 15}
#     try:
#         available = sorted(os.sched_getaffinity(0))
#         target = {cpu for cpu in available if cpu not in rt_cores}
#         target={2}
#         if target:
#             os.sched_setaffinity(0, target)
#             _LOGGER.warning("Pinned robot_app_platform to CPUs: %s", sorted(target))
#         else:
#             _LOGGER.warning("No non-RT CPUs available; leaving affinity unchanged")
#     except Exception:
#         _LOGGER.exception("Failed to set CPU affinity")


_DEV_SKIP_LOGIN = True
_SKIP_SPLASH= True


class _FramelessHeaderDrag(QObject):
    def __init__(self, window: QWidget, drag_widget: QWidget):
        super().__init__(window)
        self._window = window
        self._drag_widget = drag_widget
        self._dragging = False
        self._press_offset = QPoint()
        self._drag_widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is not self._drag_widget:
            return False

        if event.type() == QEvent.Type.MouseButtonPress:
            mouse_event = event
            if isinstance(mouse_event, QMouseEvent) and mouse_event.button() == Qt.MouseButton.LeftButton:
                self._dragging = True
                self._press_offset = mouse_event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
                return True

        if event.type() == QEvent.Type.MouseMove and self._dragging:
            mouse_event = event
            if isinstance(mouse_event, QMouseEvent):
                self._window.move(mouse_event.globalPosition().toPoint() - self._press_offset)
                return True

        if event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.Leave):
            self._dragging = False

        return False


class _StartupSplashBridge(QObject):
    state_ready = pyqtSignal(object)


def _startup_splash_stage_text(snapshot) -> str:
    extra = getattr(snapshot, "extra", {}) or {}
    readiness_state = str(extra.get("readiness_state") or getattr(snapshot, "state", "") or "").strip().lower()
    note = str(extra.get("readiness_note") or "").strip().lower()

    if readiness_state == "disconnected":
        return "Connecting to robot runtime"
    if readiness_state == "starting":
        return "Starting robot runtime"
    if readiness_state == "drive_not_ready":
        if "ethercat" in note or "sdo" in note:
            return "Checking EtherCAT communication"
        if "disabled" in note or "not motion-ready" in note or "not operation" in note:
            return "Enabling robot drives"
        return "Preparing robot drives"
    if readiness_state == "tool_mismatch":
        return "Configuring robot tool"
    if readiness_state in {"error", "fault"}:
        return "Checking robot status"
    return "Waiting for robot readiness"


class _StartupSplashCoordinator:
    def __init__(self, shell: AppShell, splash: StartupSplashView, messaging_service) -> None:
        self._shell = shell
        self._splash = splash
        self._messaging = messaging_service
        self._bridge = _StartupSplashBridge()
        self._bridge.state_ready.connect(self._apply_robot_state)
        self._active = False
        self._finished = False

    def start(self) -> None:
        if self._active:
            return
        self._messaging.subscribe(RobotTopics.STATE, self._on_robot_state)
        self._active = True

    def stop(self) -> None:
        if not self._active:
            return
        try:
            self._messaging.unsubscribe(RobotTopics.STATE, self._on_robot_state)
        finally:
            self._active = False

    def _on_robot_state(self, snapshot) -> None:
        self._bridge.state_ready.emit(snapshot)

    def _apply_robot_state(self, snapshot) -> None:
        if self._finished:
            return
        extra = getattr(snapshot, "extra", {}) or {}
        readiness_state = str(extra.get("readiness_state") or getattr(snapshot, "state", "") or "").strip().lower()
        robot_ready = extra.get("robot_ready") is True or readiness_state == "idle"

        if robot_ready:
            self._finished = True
            self._splash.set_active_step(3)
            self._splash.mark_complete()
            QTimer.singleShot(350, self._hide_splash)
            return

        self._splash.set_active_step(3)
        self._splash.set_message(_startup_splash_stage_text(snapshot))

    def _hide_splash(self) -> None:
        self.stop()
        if self._shell.stacked_widget.currentWidget() is self._splash:
            self._shell.stacked_widget.setCurrentWidget(self._shell.folders_page)
        self._shell.stacked_widget.removeWidget(self._splash)
        self._splash.deleteLater()

def main() -> None:
    setup_logging()
    # _pin_process_to_non_rt_cores()
    startup_config = load_startup_config()
    bootstrap_provider = load_bootstrap_provider(startup_config)

    logging.getLogger("MessageBroker").setLevel(logging.WARNING)
    logging.getLogger("RobotStatePublisher").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("HttpCellTransport").setLevel(logging.WARNING)
    logging.getLogger("HttpCellTransport[cell=0]").setLevel(logging.WARNING)
    logging.getLogger("HttpCellTransport[cell=1]").setLevel(logging.WARNING)
    logging.getLogger("HttpCellTransport[cell=2]").setLevel(logging.WARNING)
    logging.getLogger("WeightCellService").setLevel(logging.WARNING)

    # 1 — engine singletons
    ctx = EngineContext.build()

    ros_backend = build_ros_backend_launcher_from_env(startup_config.ros_backend)
    ros_backend.start()

    # 2 — robot app (settings loaded, services wired)
    try:
        robot_app = (
            SystemBuilder()
            .with_robot(bootstrap_provider.build_robot())
            .with_messaging_service(ctx.messaging_service)
            .build(bootstrap_provider.system_class)
        )
    except Exception:
        ros_backend.stop()
        raise

    # 3 — shell folder layout from app metadata
    ShellConfigurator.configure(bootstrap_provider.system_class)

    # 4 — Qt app + localization
    qt_app = QApplication(sys.argv)
    localization_svc = _build_localization_service(robot_app, ctx.messaging_service)
    localization_svc.set_language(localization_svc.get_language())

    # 4b — Create shell BEFORE login (empty content area, header + language selector visible)
    shell = AppShell(
        app_descriptors=[],
        widget_factory=lambda _: QWidget(),   # placeholder, never invoked during login
        languages=localization_svc.available_languages(),
    )
    shell.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
    # shell.setFixedSize(1280, 1024)
    shell.showFullScreen()
    shell._header_drag = _FramelessHeaderDrag(shell, shell.header)
    localization_svc.sync_selector(shell.header.language_selector)
    shell.header.language_selector.languageChanged.connect(localization_svc.set_language)

    if not _SKIP_SPLASH:
        startup_splash = StartupSplashView(shell)
        startup_splash.set_active_step(2)
        startup_splash.set_message("Loading applications")
        shell.stacked_widget.addWidget(startup_splash)
        shell.stacked_widget.setCurrentWidget(startup_splash)
        startup_splash_coordinator = _StartupSplashCoordinator(shell, startup_splash, ctx.messaging_service)
        notification_presenter = UserNotificationPresenter(
            shell,
            ctx.messaging_service,
            translate=lambda key: localization_svc.translate("Notifications", key),
        )
        robot_connection_notifier = RobotConnectionNotifier(ctx.messaging_service, suppress_until_ready=True)
        shell._notification_presenter = notification_presenter
        shell._robot_connection_notifier = robot_connection_notifier
        shell._startup_splash = startup_splash
        shell._startup_splash_coordinator = startup_splash_coordinator

    # Wire broker → shell navigation
    # Used to automatically open the workpiece editor when the "open in editor"
    # button is clicked in the library
    def _on_navigate(payload: dict) -> None:
        app_name = payload.get("app") if isinstance(payload, dict) else str(payload)
        if app_name:
            shell.show_app(app_name)

    ctx.messaging_service.subscribe("shell/navigate", _on_navigate)
    shell.show()

    if not _SKIP_SPLASH:
        notification_presenter.start()
        robot_connection_notifier.start()

    # 4c — Login gate
    if _DEV_SKIP_LOGIN:
        from src.applications.login.stub_login_application_service import _StubUser
        from src.engine.auth.user_session import UserSession
        session = UserSession()
        session.login(_StubUser())
        _LOGGER.warning("DEV_SKIP_LOGIN is enabled — bypassing authentication")
        _load_apps_into_shell(shell, session, robot_app, ctx, bootstrap_provider)
        if not _SKIP_SPLASH:
            startup_splash.set_active_step(3)
            startup_splash.set_message("Waiting for robot readiness")
            shell.stacked_widget.setCurrentWidget(startup_splash)
            startup_splash_coordinator.start()

    else:
        login_view = bootstrap_provider.build_login_view(robot_app, ctx.messaging_service)   # parent=None; stacked_widget becomes parent
        shell.stacked_widget.addWidget(login_view)
        shell.stacked_widget.setCurrentWidget(login_view)   # show login in shell content area

        # LanguageChange events only reach top-level windows; wire retranslation directly.
        shell.header.language_selector.languageChanged.connect(login_view.retranslateUi)

        def _on_login_accepted():
            from src.engine.auth.user_session import UserSession
            shell.header.language_selector.languageChanged.disconnect(login_view.retranslateUi)
            session = UserSession()
            session.login(login_view.result_user())
            shell.stacked_widget.removeWidget(login_view)
            login_view.deleteLater()
            _load_apps_into_shell(shell, session, robot_app, ctx, bootstrap_provider)

            if not _SKIP_SPLASH:
                startup_splash.set_active_step(3)
                startup_splash.set_message("Waiting for robot readiness")
                shell.stacked_widget.setCurrentWidget(startup_splash)
                startup_splash_coordinator.start()

        login_view.accepted.connect(_on_login_accepted)

    # # 7 — broker debug window (temporary — remove when no longer needed)
    # _debug_window = _build_broker_debug_window(ctx.messaging_service)
    # _debug_window.show()

    try:
        sys.exit(qt_app.exec())
    finally:
        if not _SKIP_SPLASH:
            startup_splash_coordinator.stop()
        robot_connection_notifier.stop()
        notification_presenter.stop()
        robot_app.stop()
        ros_backend.stop()
def _load_apps_into_shell(shell, session, robot_app, ctx, bootstrap_provider):
    """Load role-filtered apps and reload the shell's folder page."""
    auth_svc = bootstrap_provider.build_authorization_service(robot_app)
    visible_specs = auth_svc.get_visible_apps(session.current_user, robot_app.__class__.shell.applications)

    loader = ApplicationLoader(ctx.messaging_service)
    for spec in visible_specs:
        if spec.factory is None:
            _LOGGER.warning("ApplicationSpec '%s' has no factory — skipping", spec.name)
            continue
        try:
            loader.register_spec(spec, builder=lambda spec=spec: spec.factory(robot_app))
        except Exception:
            _LOGGER.exception("Failed to register application '%s'", spec.name)

    descriptors, widget_factory = loader.build_registry()
    shell._app_descriptors = descriptors
    shell._widget_factory   = widget_factory
    shell.create_folders_page()
    shell.stacked_widget.setCurrentIndex(0)


def _build_localization_service(robot_app, messaging_service) -> LocalizationService:
    module_path = Path(sys.modules[robot_app.__class__.__module__].__file__).resolve().parent
    translations_dir = module_path / robot_app.metadata.translations_root
    shared_translations_dir = Path(__file__).resolve().parent.parent / "applications" / "localization"
    state_file = module_path / robot_app.metadata.settings_root / "localization.json"
    return LocalizationService(
        [str(shared_translations_dir), str(translations_dir)],
        messaging_service=messaging_service,
        state_file=str(state_file),
    )


def _build_broker_debug_window(messaging_service):
    from PyQt6.QtWidgets import QMainWindow
    from src.applications.broker_debug.broker_debug_factory import BrokerDebugFactory
    from src.applications.broker_debug.service.broker_debug_application_service import BrokerDebugApplicationService

    widget = BrokerDebugFactory(messaging_service).build(
        BrokerDebugApplicationService(messaging_service)
    )
    window = QMainWindow()
    window.setWindowTitle("Broker Debug")
    window.setCentralWidget(widget)
    window.resize(1280, 800)
    return window


if __name__ == "__main__":
      main()

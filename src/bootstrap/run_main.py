from setproctitle import setproctitle

setproctitle("robot_app_platform")
# then continue with normal imports / startup
import logging
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PyQt6.QtCore import QObject, QEvent, QPoint, Qt, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QWidget

from src.bootstrap.logging_config import setup_logging
from src.bootstrap.build_engine import EngineContext
from src.bootstrap.application_loader import ApplicationLoader
from src.bootstrap.shell_configurator import ShellConfigurator
from src.applications.base.notification_presenter import UserNotificationPresenter
from src.applications.base.robot_connection_notifier import RobotConnectionNotifier
from src.engine.localization.localization_service import LocalizationService
from src.engine.auth.user_session import UserSession
from src.robot_systems.system_builder import SystemBuilder
from src.bootstrap.startup_config import load_bootstrap_provider, load_startup_config
from src.bootstrap.ros_backend_launcher import build_ros_backend_launcher_from_env
from src.bootstrap.shell_session_controller import ShellSessionController
from src.bootstrap.startup_splash_runtime import StartupSplashCoordinator
from pl_gui.shell.AppShell import AppShell
from pl_gui.shell.startup_splash_view import StartupSplashView

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


def _install_terminal_signal_handlers(qt_app: QApplication) -> None:
    """Route terminal shutdown signals through Qt so normal cleanup runs."""
    shutdown_requested = {"value": False}

    def _request_shutdown(signum, _frame) -> None:
        if shutdown_requested["value"]:
            return
        shutdown_requested["value"] = True
        try:
            signal_name = signal.Signals(signum).name
        except ValueError:
            signal_name = str(signum)
        _LOGGER.info("Received %s; requesting Qt application shutdown", signal_name)
        qt_app.quit()

    def _keep_python_signal_handlers_active() -> None:
        pass

    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)

    timer = QTimer(qt_app)
    timer.timeout.connect(_keep_python_signal_handlers_active)
    timer.start(200)
    qt_app._terminal_signal_timer = timer


def main() -> None:
    setup_logging()
    # _pin_process_to_non_rt_cores()
    startup_config = load_startup_config()
    dev_skip_login = startup_config.ui.dev_skip_login
    skip_splash = startup_config.ui.skip_splash
    fullscreen = startup_config.ui.fullscreen
    window_width = startup_config.ui.window_width
    window_height = startup_config.ui.window_height
    show_account_button_when_dev_skip_login = (
        startup_config.ui.show_account_button_when_dev_skip_login
    )
    show_power_off_button = startup_config.ui.show_power_off_button
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
            .with_development_mode(dev_skip_login)
            .build(bootstrap_provider.system_class)
        )
    except Exception:
        ros_backend.stop()
        raise

    # 3 — shell folder layout from app metadata
    ShellConfigurator.configure(bootstrap_provider.system_class)

    # 4 — Qt app + localization
    qt_app = QApplication(sys.argv)
    _install_terminal_signal_handlers(qt_app)
    localization_svc = _build_localization_service(robot_app, ctx.messaging_service)
    localization_svc.set_language(localization_svc.get_language())

    # 4b — Create shell BEFORE login (empty content area, header + language selector visible)
    shell = AppShell(
        app_descriptors=[],
        widget_factory=lambda _: QWidget(),   # placeholder, never invoked during login
        languages=localization_svc.available_languages(),
    )
    shell.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
    if not fullscreen:
        shell.setFixedSize(window_width, window_height)
    shell._header_drag = _FramelessHeaderDrag(shell, shell.header)
    localization_svc.sync_selector(shell.header.language_selector)
    shell.header.language_selector.languageChanged.connect(localization_svc.set_language)
    shell.header.power_toggle_button.setVisible(show_power_off_button)

    shutdown_requested = {"value": False}

    def _on_power_off_requested() -> None:
        if shutdown_requested["value"]:
            return
        shutdown_requested["value"] = True
        shell.header.power_toggle_button.setEnabled(False)
        _LOGGER.info("Platform shutdown requested from header")
        shell.close()

    shell.header.power_off_requested.connect(_on_power_off_requested)

    startup_splash_coordinator = None
    notification_presenter = None
    robot_connection_notifier = None
    if not skip_splash:
        startup_splash = StartupSplashView(shell)
        startup_splash.set_active_step(2)
        startup_splash.set_message("Loading applications")
        shell.stacked_widget.addWidget(startup_splash)
        shell.stacked_widget.setCurrentWidget(startup_splash)
        shell.header.language_selector.languageChanged.connect(startup_splash.retranslateUi)
        startup_splash_coordinator = StartupSplashCoordinator(shell, startup_splash, ctx.messaging_service)
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

    session = UserSession()
    active_login_view = {"widget": None}

    # Wire broker → shell navigation
    # Used to automatically open the workpiece editor when the "open in editor"
    # button is clicked in the library
    from src.shared_contracts.events.shell_events import ApplicationShortcut, ShellTopics

    def _on_navigate(payload: dict) -> None:
        if not session.is_authenticated():
            _LOGGER.warning("Ignoring shell navigation while logged out")
            return
        app_name = payload.get("app") if isinstance(payload, dict) else str(payload)
        visible_names = {item.name for item in getattr(shell, "_app_descriptors", [])}
        if app_name in visible_names:
            shell.show_app(app_name)
        elif app_name:
            _LOGGER.warning("Ignoring navigation to non-visible application '%s'", app_name)

    def _visible_applications(payload: object) -> list[ApplicationShortcut]:
        excluded = set()
        if isinstance(payload, dict):
            excluded = {str(name) for name in payload.get("exclude", [])}
        folder_specs = {
            item.folder_id: item for item in robot_app.__class__.shell.folders
        }
        return [
            ApplicationShortcut(
                app_name=item.name,
                label=item.name,
                icon=item.icon_str,
                folder_id=item.folder_id,
                folder_name=folder_specs[item.folder_id].display_name
                if item.folder_id in folder_specs
                else "",
                folder_translation_key=folder_specs[item.folder_id].translation_key
                if item.folder_id in folder_specs
                else "",
            )
            for item in getattr(shell, "_app_descriptors", [])
            if item.name not in excluded
        ]

    ctx.messaging_service.subscribe(ShellTopics.NAVIGATE, _on_navigate)
    ctx.messaging_service.subscribe(ShellTopics.VISIBLE_APPLICATIONS, _visible_applications)
    if fullscreen:
        shell.showFullScreen()
    else:
        shell.show()

    if not skip_splash:
        notification_presenter.start()
        robot_connection_notifier.start()

    def _show_login_view() -> None:
        login_view = bootstrap_provider.build_login_view(robot_app, ctx.messaging_service)   # parent=None; stacked_widget becomes parent
        active_login_view["widget"] = login_view
        shell.stacked_widget.addWidget(login_view)
        shell.stacked_widget.setCurrentWidget(login_view)   # show login in shell content area

        # LanguageChange events only reach top-level windows; wire retranslation directly.
        shell.header.language_selector.languageChanged.connect(login_view.retranslateUi)

        def _on_login_accepted():
            shell.header.language_selector.languageChanged.disconnect(login_view.retranslateUi)
            session_controller.login(login_view.result_user())
            active_login_view["widget"] = None
            shell.stacked_widget.removeWidget(login_view)
            login_view.deleteLater()
            _load_apps_into_shell(shell, session, robot_app, ctx, bootstrap_provider)

            if not skip_splash:
                startup_splash.set_active_step(3)
                startup_splash.set_message("Waiting for robot readiness")
                shell.stacked_widget.setCurrentWidget(startup_splash)
                startup_splash_coordinator.start()

        login_view.accepted.connect(_on_login_accepted)

    def _can_close_running_apps() -> bool:
        for app_widget in shell.running_widgets.values():
            if app_widget and hasattr(app_widget, "can_close") and not app_widget.can_close():
                return False
        return True

    session_controller = ShellSessionController(
        shell=shell,
        session=session,
        dev_skip_login=dev_skip_login,
        show_account_button_when_dev_skip_login=show_account_button_when_dev_skip_login,
        show_login_view=_show_login_view,
        can_close_running_apps=_can_close_running_apps,
    )
    session_controller.start()

    # 4c — Login gate
    if dev_skip_login:
        from src.applications.login.stub_login_application_service import _StubUser
        session_controller.login(_StubUser())
        _LOGGER.warning("ui.dev_skip_login is enabled — bypassing authentication")
        _load_apps_into_shell(shell, session, robot_app, ctx, bootstrap_provider)
        if not skip_splash:
            startup_splash.set_active_step(3)
            startup_splash.set_message("Waiting for robot readiness")
            shell.stacked_widget.setCurrentWidget(startup_splash)
            startup_splash_coordinator.start()

    else:
        _show_login_view()

    # # 7 — broker debug window (temporary — remove when no longer needed)
    # _debug_window = _build_broker_debug_window(ctx.messaging_service)
    # _debug_window.show()

    exit_code = 0
    try:
        exit_code = qt_app.exec()
    finally:
        if startup_splash_coordinator is not None:
            try:
                startup_splash_coordinator.stop()
            except Exception:
                _LOGGER.exception("Failed to stop startup splash coordinator")
        if robot_connection_notifier is not None:
            try:
                robot_connection_notifier.stop()
            except Exception:
                _LOGGER.exception("Failed to stop robot connection notifier")
        if notification_presenter is not None:
            try:
                notification_presenter.stop()
            except Exception:
                _LOGGER.exception("Failed to stop notification presenter")
        try:
            robot_app.stop()
        except Exception:
            _LOGGER.exception("Failed to stop robot system")
        try:
            ros_backend.stop()
        except Exception:
            _LOGGER.exception("Failed to stop ROS backend")
    sys.exit(exit_code)
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
    applications_dir = Path(__file__).resolve().parent.parent / "applications"
    shared_translations_dir = applications_dir / "localization"
    application_translation_dirs = sorted(
        path
        for path in applications_dir.glob("*/localization")
        if path.is_dir()
    )
    state_file = module_path / robot_app.metadata.settings_root / "localization.json"
    translation_dirs = [
        shared_translations_dir,
        *application_translation_dirs,
        translations_dir,
    ]
    return LocalizationService(
        [str(path) for path in translation_dirs],
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

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.bootstrap.logging_config import setup_logging
from src.bootstrap.build_engine import EngineContext
from src.bootstrap.application_loader import ApplicationLoader
from src.bootstrap.shell_configurator import ShellConfigurator
from src.engine.localization.localization_service import LocalizationService
from src.robot_systems.system_builder import SystemBuilder
from src.robot_systems.glue.bootstrap_provider import GlueBootstrapProvider
from PyQt6.QtWidgets import QApplication, QWidget
from pl_gui.shell.AppShell import AppShell

_LOGGER = logging.getLogger("main")
_DEV_SKIP_LOGIN = True
_BOOTSTRAP_PROVIDER = GlueBootstrapProvider()

def main() -> None:
    setup_logging()
    logging.getLogger("MessageBroker").setLevel(logging.WARNING)
    logging.getLogger("RobotStatePublisher").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    # 1 — engine singletons
    ctx = EngineContext.build()

    # 2 — robot app (settings loaded, services wired)
    robot_app = (
        SystemBuilder()
        .with_robot(_BOOTSTRAP_PROVIDER.build_robot())
        .with_messaging_service(ctx.messaging_service)
        .build(_BOOTSTRAP_PROVIDER.system_class)
    )

    # 3 — shell folder layout from app metadata
    ShellConfigurator.configure(_BOOTSTRAP_PROVIDER.system_class)

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
    localization_svc.sync_selector(shell.header.language_selector)
    shell.header.language_selector.languageChanged.connect(localization_svc.set_language)

    # Wire broker → shell navigation
    # Used to automatically open the workpiece editor when the "open in editor"
    # button is clicked in the library
    def _on_navigate(payload: dict) -> None:
        app_name = payload.get("app") if isinstance(payload, dict) else str(payload)
        if app_name:
            shell.show_app(app_name)

    ctx.messaging_service.subscribe("shell/navigate", _on_navigate)
    shell.show()

    # 4c — Login gate
    if _DEV_SKIP_LOGIN:
        from src.applications.login.stub_login_application_service import _StubUser
        from src.engine.auth.user_session import UserSession
        session = UserSession()
        session.login(_StubUser())
        _LOGGER.warning("DEV_SKIP_LOGIN is enabled — bypassing authentication")
        _load_apps_into_shell(shell, session, robot_app, ctx)
    else:
        login_view = _BOOTSTRAP_PROVIDER.build_login_view(robot_app, ctx.messaging_service)   # parent=None; stacked_widget becomes parent
        shell.stacked_widget.addWidget(login_view)          # → index 1
        shell.stacked_widget.setCurrentIndex(1)             # show login in shell content area

        # LanguageChange events only reach top-level windows; wire retranslation directly.
        shell.header.language_selector.languageChanged.connect(login_view.retranslateUi)

        def _on_login_accepted():
            from src.engine.auth.user_session import UserSession
            shell.header.language_selector.languageChanged.disconnect(login_view.retranslateUi)
            session = UserSession()
            session.login(login_view.result_user())
            shell.stacked_widget.removeWidget(login_view)
            login_view.deleteLater()
            _load_apps_into_shell(shell, session, robot_app, ctx)

        login_view.accepted.connect(_on_login_accepted)

    # # 7 — broker debug window (temporary — remove when no longer needed)
    # _debug_window = _build_broker_debug_window(ctx.messaging_service)
    # _debug_window.show()

    try:
        sys.exit(qt_app.exec())
    finally:
        robot_app.stop()
def _load_apps_into_shell(shell, session, robot_app, ctx):
    """Load role-filtered apps and reload the shell's folder page."""
    auth_svc = _BOOTSTRAP_PROVIDER.build_authorization_service(robot_app)
    visible_specs = auth_svc.get_visible_apps(session.current_user, robot_app.__class__.shell.applications)

    loader = ApplicationLoader(ctx.messaging_service)
    for spec in visible_specs:
        if spec.factory is None:
            _LOGGER.warning("ApplicationSpec '%s' has no factory — skipping", spec.name)
            continue
        try:
            application = spec.factory(robot_app)
            loader.load(application, folder_id=spec.folder_id, icon=spec.icon, name=spec.name)
        except Exception:
            _LOGGER.exception("Failed to build application '%s'", spec.name)

    descriptors, widget_factory = loader.build_registry()
    shell._app_descriptors = descriptors
    shell._widget_factory   = widget_factory
    shell.create_folders_page()
    shell.stacked_widget.setCurrentIndex(0)


def _build_localization_service(robot_app, messaging_service) -> LocalizationService:
    module_path = Path(sys.modules[robot_app.__class__.__module__].__file__).resolve().parent
    translations_dir = module_path / robot_app.metadata.translations_root
    state_file = module_path / robot_app.metadata.settings_root / "localization.json"
    return LocalizationService(
        str(translations_dir),
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

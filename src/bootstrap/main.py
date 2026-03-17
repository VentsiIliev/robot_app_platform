import logging
import sys
from pathlib import Path

from src.engine.robot.drivers.fairino import FairinoRos2Robot

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.bootstrap.logging_config import setup_logging
from src.bootstrap.build_engine import EngineContext
from src.bootstrap.application_loader import ApplicationLoader
from src.bootstrap.shell_configurator import ShellConfigurator
from src.engine.robot.drivers.fairino.test_robot import TestRobotWrapper
from src.engine.robot.drivers.fairino.fairino_robot import FairinoRobot
from src.robot_systems.system_builder import SystemBuilder
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
from PyQt6.QtWidgets import QApplication
from pl_gui.shell.AppShell import AppShell

_LOGGER = logging.getLogger("main")


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
        # .with_robot(FairinoRobot("192.168.58.2"))
        # .with_robot(TestRobotWrapper())
        .with_robot(FairinoRos2Robot(server_url="http://localhost:5000"))
        .with_messaging_service(ctx.messaging_service)
        .build(GlueRobotSystem)
    )

    # 3 — shell folder layout from app metadata
    ShellConfigurator.configure(GlueRobotSystem)

    # 4 — Qt must exist before any widgets
    qt_app = QApplication(sys.argv)

    # 4b — login gate (blocks until authenticated or user quits)
    session = _run_login(ctx, robot_app)
    if session is None:
        _LOGGER.info("Login cancelled — exiting.")
        sys.exit(0)

    # 5 — load applications
    loader = ApplicationLoader(ctx.messaging_service)
    for spec in GlueRobotSystem.shell.applications:
        if spec.factory is None:
            _LOGGER.warning("ApplicationSpec '%s' has no factory — skipping", spec.name)
            continue
        try:
            application = spec.factory(robot_app)
            loader.load(application, folder_id=spec.folder_id, icon=spec.icon, name=spec.name)
        except Exception:
            _LOGGER.exception("Failed to build application '%s'", spec.name)

    # 6 — build widget registry and launch shell
    descriptors, widget_factory = loader.build_registry()
    shell = AppShell(app_descriptors=descriptors, widget_factory=widget_factory)

    # Wire broker → shell navigation # used to automatically
    # open the workpiece editor when the "open in editor" button is clicked in the library
    def _on_navigate(payload: dict) -> None:
        app_name = payload.get("app") if isinstance(payload, dict) else str(payload)
        if app_name:
            shell.show_app(app_name)

    ctx.messaging_service.subscribe("shell/navigate", _on_navigate)
    shell.show()

    # # 7 — broker debug window (temporary — remove when no longer needed)
    # _debug_window = _build_broker_debug_window(ctx.messaging_service)
    # _debug_window.show()

    try:
        sys.exit(qt_app.exec())
    finally:
        robot_app.stop()


def _run_login(ctx, robot_app):
    """Show the login dialog and return a populated UserSession, or None if cancelled."""
    from src.applications.login.login_application_service import LoginApplicationService
    from src.applications.login.login_factory import LoginFactory
    from src.applications.user_management.domain.csv_user_repository import CsvUserRepository
    from src.engine.auth.user_session import UserSession
    from src.robot_systems.glue.application_wiring import _USERS_STORAGE
    from src.robot_systems.glue.domain.auth.authentication_service import AuthenticationService
    from src.robot_systems.glue.domain.users import GLUE_USER_SCHEMA
    from src.robot_systems.glue.service_ids import ServiceID

    user_repo    = CsvUserRepository(_USERS_STORAGE, GLUE_USER_SCHEMA)
    auth_service = AuthenticationService(user_repo)
    robot_service = robot_app.get_optional_service(ServiceID.ROBOT)

    login_service = LoginApplicationService(
        auth_service=auth_service,
        user_repository=user_repo,
        robot_service=robot_service,
    )

    dialog = LoginFactory.build(login_service, messaging=ctx.messaging_service)
    result = dialog.exec()

    if result != dialog.DialogCode.Accepted:
        return None

    session = UserSession()
    session.login(dialog.result_user())
    return session


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

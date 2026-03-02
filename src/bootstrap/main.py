import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.bootstrap.logging_config import setup_logging

_LOGGER = logging.getLogger("main")


def main() -> None:
    setup_logging()
    logging.getLogger("MessageBroker").setLevel(logging.WARNING)
    logging.getLogger("RobotStatePublisher").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    from PyQt6.QtWidgets import QApplication, QMainWindow
    from pl_gui.shell.AppShell import AppShell
    from src.bootstrap.build_engine import EngineContext
    from src.bootstrap.application_loader import ApplicationLoader
    from src.bootstrap.shell_configurator import ShellConfigurator
    from src.engine.robot.drivers.fairino.test_robot import TestRobotWrapper
    from src.robot_systems.system_builder import SystemBuilder
    from src.robot_systems.glue.glue_robot_system import GlueRobotSystem

    # 1 — engine singletons
    ctx = EngineContext.build()

    # 2 — robot app (settings loaded, services wired)
    robot_app = (
        SystemBuilder()
        .with_robot(TestRobotWrapper())
        .with_messaging_service(ctx.messaging_service)
        .build(GlueRobotSystem)
    )

    # 3 — shell folder layout from app metadata
    ShellConfigurator.configure(GlueRobotSystem)

    # 4 — Qt must exist before any widgets
    qt_app = QApplication(sys.argv)

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
    shell.show()

    # 7 — broker debug window (temporary — remove when no longer needed)
    _debug_window = _build_broker_debug_window(ctx.messaging_service)
    _debug_window.show()

    try:
        sys.exit(qt_app.exec())
    finally:
        robot_app.stop()


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

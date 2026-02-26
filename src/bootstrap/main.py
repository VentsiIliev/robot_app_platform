import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

_LOGGER = logging.getLogger("main")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    setup_logging()
    logging.getLogger("MessageBroker").setLevel(logging.WARNING)
    logging.getLogger("RobotStatePublisher").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    from PyQt6.QtWidgets import QApplication
    from pl_gui.shell.AppShell import AppShell
    from src.bootstrap.build_engine import EngineContext
    from src.bootstrap.plugin_loader import PluginLoader
    from src.bootstrap.shell_configurator import ShellConfigurator
    from src.engine.robot.drivers.fairino.test_robot import TestRobotWrapper
    from src.robot_apps.app_builder import AppBuilder
    from src.robot_apps.glue.glue_robot_app import GlueRobotApp

    # 1 — engine singletons
    ctx = EngineContext.build()

    # 2 — robot app (settings loaded, services wired)
    robot_app = (
        AppBuilder()
        .with_robot(TestRobotWrapper())
        .with_messaging_service(ctx.messaging_service)
        .build(GlueRobotApp)
    )

    # 3 — shell folder layout from app metadata
    ShellConfigurator.configure(GlueRobotApp)

    # 4 — Qt must exist before any widgets
    qt_app = QApplication(sys.argv)

    # 5 — load plugins — factory lives on each PluginSpec, bootstrap knows nothing
    loader = PluginLoader(ctx.messaging_service)
    for spec in GlueRobotApp.shell.plugins:
        if spec.factory is None:
            _LOGGER.warning("PluginSpec '%s' has no factory — skipping", spec.name)
            continue
        try:
            plugin = spec.factory(robot_app)
            loader.load(plugin, folder_id=spec.folder_id, icon=spec.icon, name=spec.name)  # ← pass name
        except Exception:
            _LOGGER.exception("Failed to build plugin '%s'", spec.name)

    # 6 — build widget registry and launch shell
    descriptors, widget_factory = loader.build_registry()
    shell = AppShell(app_descriptors=descriptors, widget_factory=widget_factory)
    shell.show()

    try:
        sys.exit(qt_app.exec())
    finally:
        robot_app.stop()


if __name__ == "__main__":
    main()

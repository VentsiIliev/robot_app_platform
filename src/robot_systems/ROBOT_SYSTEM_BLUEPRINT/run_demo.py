from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from PyQt6.QtWidgets import QApplication, QWidget
import logging
from pl_gui.shell.AppShell import AppShell
from src.bootstrap.application_loader import ApplicationLoader
from src.bootstrap.build_engine import EngineContext
from src.bootstrap.logging_config import setup_logging
from src.bootstrap.shell_configurator import ShellConfigurator
from src.engine.auth.user_session import UserSession
from src.engine.localization.localization_service import LocalizationService
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.bootstrap_provider import (
    MyRobotSystemBootstrapProvider,
)
from src.robot_systems.system_builder import SystemBuilder


def run_demo() -> None:
    setup_logging()
    logging.getLogger("MessageBroker").setLevel(logging.WARNING)
    logging.getLogger("RobotStatePublisher").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    provider = MyRobotSystemBootstrapProvider()
    ctx = EngineContext.build()

    robot_system = (
        SystemBuilder()
        .with_robot(provider.build_robot())
        .with_messaging_service(ctx.messaging_service)
        .build(provider.system_class)
    )

    ShellConfigurator.configure(provider.system_class)

    qt_app = QApplication(sys.argv)
    localization_service = _build_localization_service(robot_system, ctx.messaging_service)
    localization_service.set_language(localization_service.get_language())

    shell = AppShell(
        app_descriptors=[],
        widget_factory=lambda _: QWidget(),
        languages=localization_service.available_languages(),
    )
    localization_service.sync_selector(shell.header.language_selector)
    shell.header.language_selector.languageChanged.connect(localization_service.set_language)
    shell.show()

    session = UserSession()
    login_view = provider.build_login_view(robot_system, ctx.messaging_service)
    shell.stacked_widget.addWidget(login_view)
    shell.stacked_widget.setCurrentIndex(1)
    shell.header.language_selector.languageChanged.connect(login_view.retranslateUi)

    def _on_login_accepted():
        shell.header.language_selector.languageChanged.disconnect(login_view.retranslateUi)
        session.login(login_view.result_user())
        shell.stacked_widget.removeWidget(login_view)
        login_view.deleteLater()
        _load_apps_into_shell(shell, session, robot_system, ctx, provider)

    login_view.accepted.connect(_on_login_accepted)

    try:
        sys.exit(qt_app.exec())
    finally:
        robot_system.stop()


def _load_apps_into_shell(shell, session, robot_system, ctx, provider) -> None:
    authorization_service = provider.build_authorization_service(robot_system)
    visible_specs = authorization_service.get_visible_apps(
        session.current_user,
        robot_system.__class__.shell.applications,
    )

    loader = ApplicationLoader(ctx.messaging_service)
    for spec in visible_specs:
        if spec.factory is None:
            continue
        application = spec.factory(robot_system)
        loader.load(application, folder_id=spec.folder_id, icon=spec.icon, name=spec.name)

    descriptors, widget_factory = loader.build_registry()
    shell._app_descriptors = descriptors
    shell._widget_factory = widget_factory
    shell.create_folders_page()
    shell.stacked_widget.setCurrentIndex(0)


def _build_localization_service(robot_system, messaging_service) -> LocalizationService:
    module_path = Path(__file__).resolve().parent
    translations_dir = module_path / robot_system.metadata.translations_root
    state_file = module_path / robot_system.metadata.settings_root / "localization.json"
    return LocalizationService(
        str(translations_dir),
        messaging_service=messaging_service,
        state_file=str(state_file),
    )


if __name__ == "__main__":
    run_demo()

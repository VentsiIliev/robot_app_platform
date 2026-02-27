import logging
from typing import Type

from pl_gui.shell.shell_config import ShellConfig, FolderDefinition, create_custom_folder
from src.robot_systems.base_robot_system import BaseRobotSystem

_LOGGER = logging.getLogger("ShellConfigurator")


class ShellConfigurator:
    """
    Reads ShellSetup metadata from a BaseRobotSystem and configures
    the pl_gui ShellConfig. Called once at bootstrap before AppShell is created.
    """

    @staticmethod
    def configure(app_class: Type[BaseRobotSystem]) -> None:
        setup = app_class.shell

        if not setup.folders:
            _LOGGER.debug("No shell folders declared — using ShellConfig defaults")
            ShellConfig.initialize_defaults()
            return

        ShellConfig.clear_folders()

        for spec in setup.folders:
            folder = create_custom_folder(
                folder_id=spec.folder_id,
                name=spec.name,
                display_name=spec.display_name,
                translation_key=spec.translation_key,
            )
            ShellConfig.add_folder(folder, override_defaults=True)
            _LOGGER.info("Registered shell folder: %s (id=%s)", spec.display_name, spec.folder_id)

        _LOGGER.info(
            "%s: configured %d folders",
            app_class.metadata.name,
            len(ShellConfig.get_folders()),
        )
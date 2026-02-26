import unittest
from unittest.mock import patch, MagicMock

from src.bootstrap.shell_configurator import ShellConfigurator
from src.robot_apps.base_robot_app import (
    AppMetadata, BaseRobotApp, FolderSpec, ShellSetup,
)


# ---------------------------------------------------------------------------
# Minimal concrete app stubs
# ---------------------------------------------------------------------------

class _AppWithFolders(BaseRobotApp):
    metadata = AppMetadata(name="TestApp")
    shell    = ShellSetup(folders=[
        FolderSpec(folder_id=1, name="PROD",    display_name="Production"),
        FolderSpec(folder_id=2, name="SERVICE", display_name="Service"),
        FolderSpec(folder_id=3, name="ADMIN",   display_name="Administration"),
    ])
    settings_specs = []
    services       = []

    def on_start(self) -> None: pass
    def on_stop(self)  -> None: pass


class _AppWithNoFolders(BaseRobotApp):
    metadata = AppMetadata(name="EmptyApp")
    shell    = ShellSetup(folders=[])
    settings_specs = []
    services       = []

    def on_start(self) -> None: pass
    def on_stop(self)  -> None: pass


# ---------------------------------------------------------------------------
# ShellConfigurator.configure()
# ---------------------------------------------------------------------------

class TestShellConfiguratorWithFolders(unittest.TestCase):

    def setUp(self):
        from pl_gui.shell.shell_config import ShellConfig
        ShellConfig.clear_folders()

    def test_configure_clears_previous_folders(self):
        from pl_gui.shell.shell_config import ShellConfig
        ShellConfigurator.configure(_AppWithFolders)
        # Re-configure with different app — should not accumulate
        ShellConfigurator.configure(_AppWithFolders)
        self.assertEqual(len(ShellConfig.get_folders()), 3)

    def test_configure_registers_correct_count(self):
        from pl_gui.shell.shell_config import ShellConfig
        ShellConfigurator.configure(_AppWithFolders)
        self.assertEqual(len(ShellConfig.get_folders()), 3)

    def test_configure_registers_correct_folder_ids(self):
        from pl_gui.shell.shell_config import ShellConfig
        ShellConfigurator.configure(_AppWithFolders)
        ids = [f.id for f in ShellConfig.get_folders()]
        self.assertIn(1, ids)
        self.assertIn(2, ids)
        self.assertIn(3, ids)

    def test_configure_registers_correct_display_names(self):
        from pl_gui.shell.shell_config import ShellConfig
        ShellConfigurator.configure(_AppWithFolders)
        names = [f.display_name for f in ShellConfig.get_folders()]
        self.assertIn("Production",    names)
        self.assertIn("Service",       names)
        self.assertIn("Administration", names)

    def test_configure_folder_names(self):
        from pl_gui.shell.shell_config import ShellConfig
        ShellConfigurator.configure(_AppWithFolders)
        names = [f.name for f in ShellConfig.get_folders()]
        self.assertIn("PROD",    names)
        self.assertIn("SERVICE", names)
        self.assertIn("ADMIN",   names)


class TestShellConfiguratorNoFolders(unittest.TestCase):

    def setUp(self):
        from pl_gui.shell.shell_config import ShellConfig
        ShellConfig.clear_folders()
        ShellConfig._initialized = False

    def test_configure_no_folders_initializes_defaults(self):
        from pl_gui.shell.shell_config import ShellConfig
        ShellConfigurator.configure(_AppWithNoFolders)
        # defaults are initialized — folders list is non-empty
        self.assertGreater(len(ShellConfig.get_folders()), 0)


class TestShellConfiguratorGlueApp(unittest.TestCase):

    def setUp(self):
        from pl_gui.shell.shell_config import ShellConfig
        ShellConfig.clear_folders()

    def test_glue_app_registers_three_folders(self):
        from pl_gui.shell.shell_config import ShellConfig
        from src.robot_apps.glue.glue_robot_app import GlueRobotApp
        ShellConfigurator.configure(GlueRobotApp)
        self.assertEqual(len(ShellConfig.get_folders()), 3)

    def test_glue_app_registers_production_folder(self):
        from pl_gui.shell.shell_config import ShellConfig
        from src.robot_apps.glue.glue_robot_app import GlueRobotApp
        ShellConfigurator.configure(GlueRobotApp)
        ids = [f.id for f in ShellConfig.get_folders()]
        self.assertIn(1, ids)

    def test_glue_app_registers_service_folder(self):
        from pl_gui.shell.shell_config import ShellConfig
        from src.robot_apps.glue.glue_robot_app import GlueRobotApp
        ShellConfigurator.configure(GlueRobotApp)
        ids = [f.id for f in ShellConfig.get_folders()]
        self.assertIn(2, ids)

    def test_glue_app_registers_admin_folder(self):
        from pl_gui.shell.shell_config import ShellConfig
        from src.robot_apps.glue.glue_robot_app import GlueRobotApp
        ShellConfigurator.configure(GlueRobotApp)
        ids = [f.id for f in ShellConfig.get_folders()]
        self.assertIn(3, ids)

    def test_configure_is_idempotent(self):
        from pl_gui.shell.shell_config import ShellConfig
        from src.robot_apps.glue.glue_robot_app import GlueRobotApp
        ShellConfigurator.configure(GlueRobotApp)
        ShellConfigurator.configure(GlueRobotApp)
        self.assertEqual(len(ShellConfig.get_folders()), 3)


if __name__ == "__main__":
    unittest.main()
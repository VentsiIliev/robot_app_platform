import sys
import unittest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Patch targets — all imports inside main() are lazy, patch at source module
# ---------------------------------------------------------------------------

_PATCH_QT_APP     = "PyQt6.QtWidgets.QApplication"
_PATCH_APP_SHELL  = "pl_gui.shell.AppShell.AppShell"
_PATCH_ENGINE_CTX = "src.bootstrap.build_engine.EngineContext"
_PATCH_LOADER     = "src.bootstrap.plugin_loader.PluginLoader"
_PATCH_SHELL_CFG  = "src.bootstrap.shell_configurator.ShellConfigurator"
_PATCH_ROBOT      = "src.engine.robot.drivers.fairino.test_robot.TestRobotWrapper"
_PATCH_BUILDER    = "src.robot_apps.app_builder.AppBuilder"
_PATCH_GLUE_APP   = "src.robot_apps.glue.glue_robot_app.GlueRobotApp"
_PATCH_SYS_EXIT   = "sys.exit"


# ---------------------------------------------------------------------------
# Helper — build all standard mocks and run main()
# ---------------------------------------------------------------------------

def _run_main(plugins=None, extra_patches=None):
    """
    Patch all external dependencies and call main().
    Returns a dict of the key mocks for assertion.
    Catches SystemExit so tests don't abort.
    """
    mock_ms        = MagicMock()
    mock_ctx       = MagicMock()
    mock_ctx.messaging_service = mock_ms

    mock_robot_app = MagicMock()
    mock_robot_app.stop = MagicMock()

    mock_builder   = MagicMock()
    mock_builder.with_robot.return_value              = mock_builder
    mock_builder.with_messaging_service.return_value  = mock_builder
    mock_builder.build.return_value                   = mock_robot_app

    mock_loader    = MagicMock()
    mock_loader.build_registry.return_value = ([], MagicMock())

    mock_qt_inst   = MagicMock()
    mock_qt_inst.exec.return_value = 0

    mock_app_cls         = MagicMock()
    mock_app_cls.shell.plugins = plugins if plugins is not None else []
    mock_app_cls.metadata.name = "GlueApplication"

    patches = {
        _PATCH_QT_APP:     MagicMock(return_value=mock_qt_inst),
        _PATCH_APP_SHELL:  MagicMock(),
        _PATCH_ENGINE_CTX: MagicMock(build=MagicMock(return_value=mock_ctx)),
        _PATCH_LOADER:     MagicMock(return_value=mock_loader),
        _PATCH_SHELL_CFG:  MagicMock(),
        _PATCH_ROBOT:      MagicMock(),
        _PATCH_BUILDER:    MagicMock(return_value=mock_builder),
        _PATCH_GLUE_APP:   mock_app_cls,
        _PATCH_SYS_EXIT:   MagicMock(side_effect=SystemExit(0)),
    }
    if extra_patches:
        patches.update(extra_patches)

    with patch.multiple("", **{k: patch(k) for k in patches}):
        active = {k: patch(k, v) for k, v in patches.items()}
        started = {k: p.start() for k, p in active.items()}
        try:
            from src.bootstrap.main import main
            try:
                main()
            except SystemExit:
                pass
        finally:
            for p in active.values():
                p.stop()

    return {
        "ctx":             mock_ctx,
        "robot_app":       mock_robot_app,
        "loader":          mock_loader,
        "shell_cfg":       started.get(_PATCH_SHELL_CFG),
        "builder":         mock_builder,
        "messaging_svc":   mock_ms,
        "app_cls":         mock_app_cls,
        "engine_ctx_mock": started.get(_PATCH_ENGINE_CTX),
    }


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------

class TestSetupLogging(unittest.TestCase):

    def test_setup_logging_does_not_raise(self):
        from src.bootstrap.main import setup_logging
        setup_logging()

    def test_setup_logging_sets_debug_level(self):
        import logging
        from src.bootstrap.main import setup_logging
        setup_logging()
        self.assertEqual(logging.getLogger().level, logging.DEBUG)


# ---------------------------------------------------------------------------
# main() — wiring logic tests (all Qt/GUI/robot patched)
# ---------------------------------------------------------------------------

class TestMainIntegration(unittest.TestCase):

    # ── helper to run one isolated test ──────────────────────────────────

    @staticmethod
    def _patch_and_run(plugins=None, override=None):
        """Run main() with minimal patches and return mocks."""
        mock_ms        = MagicMock()
        mock_ctx       = MagicMock()
        mock_ctx.messaging_service = mock_ms

        mock_robot_app = MagicMock()
        mock_robot_app.stop = MagicMock()

        mock_builder   = MagicMock()
        mock_builder.with_robot.return_value              = mock_builder
        mock_builder.with_messaging_service.return_value  = mock_builder
        mock_builder.build.return_value                   = mock_robot_app

        mock_loader    = MagicMock()
        mock_loader.build_registry.return_value = ([], MagicMock())

        mock_app_cls         = MagicMock()
        mock_app_cls.shell.plugins = plugins if plugins is not None else []
        mock_app_cls.metadata.name = "GlueApplication"

        mock_engine_cls = MagicMock()
        mock_engine_cls.build.return_value = mock_ctx

        mock_builder_cls = MagicMock(return_value=mock_builder)
        mock_loader_cls  = MagicMock(return_value=mock_loader)
        mock_shell_cfg   = MagicMock()

        with patch(_PATCH_QT_APP,    MagicMock(return_value=MagicMock(exec=MagicMock(return_value=0)))), \
             patch(_PATCH_APP_SHELL, MagicMock()), \
             patch(_PATCH_ENGINE_CTX, mock_engine_cls), \
             patch(_PATCH_LOADER,     mock_loader_cls), \
             patch(_PATCH_SHELL_CFG,  mock_shell_cfg), \
             patch(_PATCH_ROBOT,      MagicMock()), \
             patch(_PATCH_BUILDER,    mock_builder_cls), \
             patch(_PATCH_GLUE_APP,   mock_app_cls), \
             patch(_PATCH_SYS_EXIT,   MagicMock(side_effect=SystemExit(0))):
            from src.bootstrap.main import main
            try:
                main()
            except SystemExit:
                pass

        return {
            "engine_cls":  mock_engine_cls,
            "robot_app":   mock_robot_app,
            "loader":      mock_loader,
            "loader_cls":  mock_loader_cls,
            "shell_cfg":   mock_shell_cfg,
            "builder":     mock_builder,
            "ms":          mock_ms,
            "app_cls":     mock_app_cls,
        }

    # ── tests ──────────────────────────────────────────────────────────

    def test_engine_context_built(self):
        mocks = self._patch_and_run()
        mocks["engine_cls"].build.assert_called_once()

    def test_shell_configurator_called_with_app_class(self):
        mocks = self._patch_and_run()
        mocks["shell_cfg"].configure.assert_called_once_with(mocks["app_cls"])

    def test_plugin_loader_receives_messaging_service(self):
        mocks = self._patch_and_run()
        mocks["loader_cls"].assert_called_once_with(mocks["ms"])

    def test_plugin_loader_load_called_per_spec(self):
        spec1 = MagicMock()
        spec1.factory   = MagicMock(return_value=MagicMock())
        spec1.folder_id = 1
        spec1.icon      = "fa5s.cog"
        spec1.name      = "Plugin1"

        spec2 = MagicMock()
        spec2.factory   = MagicMock(return_value=MagicMock())
        spec2.folder_id = 2
        spec2.icon      = "fa5s.star"
        spec2.name      = "Plugin2"

        mocks = self._patch_and_run(plugins=[spec1, spec2])
        self.assertEqual(mocks["loader"].load.call_count, 2)

    def test_spec_with_no_factory_is_skipped(self):
        spec = MagicMock()
        spec.factory = None
        spec.name    = "NoFactory"
        mocks = self._patch_and_run(plugins=[spec])
        mocks["loader"].load.assert_not_called()

    def test_robot_app_stop_called_on_exit(self):
        mocks = self._patch_and_run()
        mocks["robot_app"].stop.assert_called_once()

    def test_build_registry_called_once(self):
        mocks = self._patch_and_run()
        mocks["loader"].build_registry.assert_called_once()

    def test_builder_receives_messaging_service(self):
        mocks = self._patch_and_run()
        mocks["builder"].with_messaging_service.assert_called_once_with(mocks["ms"])

    def test_spec_factory_called_with_robot_app(self):
        spec = MagicMock()
        spec.factory   = MagicMock(return_value=MagicMock())
        spec.folder_id = 1
        spec.icon      = "fa5s.cog"
        spec.name      = "TestPlugin"
        mocks = self._patch_and_run(plugins=[spec])
        spec.factory.assert_called_once_with(mocks["robot_app"])

    def test_failing_plugin_factory_does_not_abort_loop(self):
        spec_bad = MagicMock()
        spec_bad.factory   = MagicMock(side_effect=RuntimeError("crash"))
        spec_bad.folder_id = 1
        spec_bad.icon      = "fa5s.cog"
        spec_bad.name      = "BadPlugin"

        spec_good = MagicMock()
        spec_good.factory   = MagicMock(return_value=MagicMock())
        spec_good.folder_id = 1
        spec_good.icon      = "fa5s.star"
        spec_good.name      = "GoodPlugin"

        mocks = self._patch_and_run(plugins=[spec_bad, spec_good])
        # good plugin's factory still called
        spec_good.factory.assert_called_once()

    def test_loader_load_passes_correct_folder_id(self):
        spec = MagicMock()
        spec.factory   = MagicMock(return_value=MagicMock())
        spec.folder_id = 7
        spec.icon      = "fa5s.cog"
        spec.name      = "FolderTest"
        mocks = self._patch_and_run(plugins=[spec])
        call_kwargs = mocks["loader"].load.call_args[1]
        self.assertEqual(call_kwargs.get("folder_id", mocks["loader"].load.call_args[0][1] if len(mocks["loader"].load.call_args[0]) > 1 else None), 7)

    def test_loader_load_passes_plugin_name(self):
        spec = MagicMock()
        spec.factory   = MagicMock(return_value=MagicMock())
        spec.folder_id = 1
        spec.icon      = "fa5s.cog"
        spec.name      = "NamedPlugin"
        mocks = self._patch_and_run(plugins=[spec])
        call_kwargs = mocks["loader"].load.call_args[1]
        self.assertEqual(call_kwargs.get("name"), "NamedPlugin")


if __name__ == "__main__":
    unittest.main()

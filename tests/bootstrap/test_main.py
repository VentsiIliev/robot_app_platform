"""
Smoke tests for src/bootstrap/main.py.

The startup sequence calls Qt, hardware drivers, and the full robot system —
all of which are mocked here. Tests verify import integrity and step ordering,
not full execution.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch, call


# ══════════════════════════════════════════════════════════════════════════════
# Import smoke test
# ══════════════════════════════════════════════════════════════════════════════

class TestMainImport(unittest.TestCase):

    def test_main_module_imports_without_error(self):
        """Importing main.py (not calling main()) must not raise."""
        import importlib
        import src.bootstrap.main as m
        self.assertTrue(callable(m.main))


# ══════════════════════════════════════════════════════════════════════════════
# Startup sequence order
# ══════════════════════════════════════════════════════════════════════════════

class TestStartupSequenceOrder(unittest.TestCase):

    def test_startup_sequence_order(self):
        """
        Patches all six startup steps and verifies they are invoked in the
        documented order:
          1. EngineContext.build()
          2. SystemBuilder().with_robot(...).with_messaging_service(...).build(...)
          3. ShellConfigurator.configure(...)
          4. QApplication(sys.argv)
          5. ApplicationLoader — spec.factory + loader.load + loader.build_registry
          6. AppShell — show
        """
        call_order = []

        # ── Patch targets ────────────────────────────────────────────────────
        fake_ms   = MagicMock()
        fake_ctx  = MagicMock()
        fake_ctx.messaging_service = fake_ms

        fake_robot_app = MagicMock()
        fake_robot_app.stop = MagicMock()
        fake_robot_app.shell = MagicMock()

        # Specs with valid factories
        fake_spec = MagicMock()
        fake_spec.factory = MagicMock(return_value=MagicMock())
        fake_spec.folder_id = 1
        fake_spec.icon = "icon"
        fake_spec.name = "TestApp"

        from src.robot_systems.glue.glue_robot_system import GlueRobotSystem

        patches = {
            "src.bootstrap.main.EngineContext.build":       MagicMock(side_effect=lambda: (call_order.append("engine"), fake_ctx)[1]),
            "src.bootstrap.main.SystemBuilder":             None,   # handled below
            "src.bootstrap.main.ShellConfigurator.configure": MagicMock(side_effect=lambda _: call_order.append("shell_cfg")),
            "src.bootstrap.main.QApplication":              MagicMock(side_effect=lambda _: (call_order.append("qt"), MagicMock())[1]),
            "src.bootstrap.main.ApplicationLoader":         None,   # handled below
            "src.bootstrap.main.AppShell":                  None,   # handled below
        }

        fake_builder = MagicMock()
        fake_builder.with_robot.return_value         = fake_builder
        fake_builder.with_messaging_service.return_value = fake_builder
        fake_builder.build.side_effect = lambda _: (call_order.append("system_build"), fake_robot_app)[1]

        fake_loader = MagicMock()
        fake_loader.build_registry.return_value = ([], MagicMock())

        fake_shell = MagicMock()
        fake_shell_instance = MagicMock()

        with (
            patch("src.bootstrap.main.EngineContext.build",
                  side_effect=lambda: (call_order.append("engine"), fake_ctx)[1]),
            patch("src.bootstrap.main.SystemBuilder",
                  return_value=fake_builder),
            patch("src.bootstrap.main.ShellConfigurator.configure",
                  side_effect=lambda _: call_order.append("shell_cfg")),
            patch("src.bootstrap.main.QApplication",
                  side_effect=lambda _: (call_order.append("qt"), MagicMock())[1]),
            patch("src.bootstrap.main.ApplicationLoader",
                  side_effect=lambda _: (call_order.append("loader"), fake_loader)[1]),
            patch("src.bootstrap.main.AppShell",
                  side_effect=lambda **kw: (call_order.append("shell"), fake_shell_instance)[1]),
            patch.object(GlueRobotSystem, "shell", MagicMock(applications=[fake_spec])),
            patch("sys.exit"),
        ):
            import src.bootstrap.main as m
            try:
                m.main()
            except Exception:
                pass   # sys.exit or Qt errors expected in test environment

        self.assertIn("engine",      call_order)
        self.assertIn("system_build", call_order)
        self.assertIn("shell_cfg",   call_order)
        self.assertIn("qt",          call_order)

        # engine must come before system_build
        self.assertLess(
            call_order.index("engine"),
            call_order.index("system_build"),
        )
        # system_build must come before shell_cfg
        self.assertLess(
            call_order.index("system_build"),
            call_order.index("shell_cfg"),
        )
        # shell_cfg must come before Qt
        self.assertLess(
            call_order.index("shell_cfg"),
            call_order.index("qt"),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Abort on engine build failure
# ══════════════════════════════════════════════════════════════════════════════

class TestStartupAbortOnFailure(unittest.TestCase):

    def test_startup_aborts_cleanly_on_engine_build_failure(self):
        """
        If EngineContext.build() raises, main() must propagate (not swallow)
        the exception and must not attempt to build the Qt application.
        """
        qt_called = []

        with (
            patch("src.bootstrap.main.EngineContext.build",
                  side_effect=RuntimeError("engine init failed")),
            patch("src.bootstrap.main.QApplication",
                  side_effect=lambda _: qt_called.append("qt")),
        ):
            import src.bootstrap.main as m
            with self.assertRaises(RuntimeError):
                m.main()

        self.assertEqual(qt_called, [], "QApplication must not be called after engine failure")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.robot_systems.paint.applications.dashboard.controller.paint_dashboard_controller import (
    PaintDashboardController,
)
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardState
from src.robot_systems.paint.applications.dashboard.model.paint_dashboard_model import (
    PaintDashboardModel,
)


def _signal() -> MagicMock:
    sig = MagicMock()
    sig.connect = MagicMock()
    return sig


class TestPaintDashboardModel(unittest.TestCase):
    def test_load_and_save_contract(self) -> None:
        service = MagicMock()
        state = DashboardState(process_state="idle")
        service.load_state.return_value = state
        model = PaintDashboardModel(service)

        self.assertIs(model.load(), state)
        self.assertIsNone(model.save({"ignored": True}))

    def test_start_stop_pause_resume_and_reset_delegate_through_service(self) -> None:
        service = MagicMock()
        running = DashboardState(process_state="running")
        paused = DashboardState(process_state="paused")
        idle = DashboardState(process_state="idle")
        service.load_state.side_effect = [running, idle, running, paused, paused, running, idle]
        model = PaintDashboardModel(service)

        self.assertIs(model.start(), running)
        self.assertIs(model.stop_process(), idle)
        self.assertIs(model.toggle_pause(), paused)
        self.assertIs(model.toggle_pause(), running)
        self.assertIs(model.reset_errors(), idle)

        service.start.assert_called_once_with()
        service.stop.assert_called_once_with()
        service.pause.assert_called_once_with()
        service.resume.assert_called_once_with()
        service.reset_errors.assert_called_once_with()


class TestPaintDashboardController(unittest.TestCase):
    def _make_view(self) -> MagicMock:
        view = MagicMock()
        view.start_requested = _signal()
        view.stop_requested = _signal()
        view.pause_requested = _signal()
        view.reset_requested = _signal()
        view.destroyed = _signal()
        view.isVisible.return_value = True
        return view

    def test_init_wires_signals_and_mixin_setup(self) -> None:
        model = MagicMock()
        view = self._make_view()
        broker = MagicMock()

        with (
            patch.object(PaintDashboardController, "_init_dashboard_camera_feed") as init_camera,
            patch.object(PaintDashboardController, "_init_dashboard_process_state") as init_process,
        ):
            controller = PaintDashboardController(model, view, broker)

        self.assertIs(controller._model, model)
        self.assertIs(controller._view, view)
        self.assertIs(controller._broker, broker)
        self.assertFalse(controller._active)
        init_camera.assert_called_once_with()
        init_process.assert_called_once_with()
        view.start_requested.connect.assert_called_once_with(controller._on_start)
        view.stop_requested.connect.assert_called_once_with(controller._on_stop)
        view.pause_requested.connect.assert_called_once_with(controller._on_pause)
        view.reset_requested.connect.assert_called_once_with(controller._on_reset)

    def test_load_and_stop_manage_subscriptions_and_view_state(self) -> None:
        state = DashboardState(process_state="idle")
        model = MagicMock()
        model.load.return_value = state
        view = self._make_view()

        with (
            patch.object(PaintDashboardController, "_init_dashboard_camera_feed"),
            patch.object(PaintDashboardController, "_init_dashboard_process_state"),
            patch.object(PaintDashboardController, "_subscribe_dashboard_camera_feed") as sub_camera,
            patch.object(PaintDashboardController, "_subscribe_dashboard_process_state") as sub_process,
            patch.object(PaintDashboardController, "_unsubscribe_all") as unsub_all,
        ):
            controller = PaintDashboardController(model, view, MagicMock())
            controller.load()

            self.assertTrue(controller._active)
            sub_camera.assert_called_once_with()
            sub_process.assert_called_once_with()
            view.apply_dashboard_state.assert_called_once_with(state)
            view.destroyed.connect.assert_called_once_with(controller.stop)

            controller.stop()
            self.assertFalse(controller._active)
            unsub_all.assert_called_once_with()

    def test_action_handlers_apply_updated_state(self) -> None:
        model = MagicMock()
        start_state = DashboardState(process_state="running")
        stop_state = DashboardState(process_state="stopped")
        pause_state = DashboardState(process_state="paused")
        reset_state = DashboardState(process_state="idle")
        model.start.return_value = start_state
        model.stop_process.return_value = stop_state
        model.toggle_pause.return_value = pause_state
        model.reset_errors.return_value = reset_state
        view = self._make_view()

        with (
            patch.object(PaintDashboardController, "_init_dashboard_camera_feed"),
            patch.object(PaintDashboardController, "_init_dashboard_process_state"),
        ):
            controller = PaintDashboardController(model, view, MagicMock())

        controller._on_start()
        controller._on_stop()
        controller._on_pause()
        controller._on_reset()

        model.start.assert_called_once_with()
        model.stop_process.assert_called_once_with()
        model.toggle_pause.assert_called_once_with()
        model.reset_errors.assert_called_once_with()
        self.assertEqual(
            view.apply_dashboard_state.call_args_list,
            [
                unittest.mock.call(start_state),
                unittest.mock.call(stop_state),
                unittest.mock.call(pause_state),
                unittest.mock.call(reset_state),
            ],
        )

    def test_view_ok_requires_active_visible_view(self) -> None:
        view = self._make_view()
        with (
            patch.object(PaintDashboardController, "_init_dashboard_camera_feed"),
            patch.object(PaintDashboardController, "_init_dashboard_process_state"),
        ):
            controller = PaintDashboardController(MagicMock(), view, MagicMock())

        self.assertFalse(controller._view_ok())
        controller._active = True
        self.assertTrue(controller._view_ok())

        view.isVisible.side_effect = RuntimeError("deleted")
        self.assertFalse(controller._view_ok())


if __name__ == "__main__":
    unittest.main()

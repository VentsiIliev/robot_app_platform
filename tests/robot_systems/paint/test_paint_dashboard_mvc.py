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
from src.robot_systems.paint.processes.paint.dashboard_live_view_events import (
    PaintDashboardLiveViewEvent,
    PaintDashboardLiveViewTopics,
)
from src.shared_contracts.events.robot_events import RobotTopics


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
            patch.object(PaintDashboardController, "_subscribe_dashboard_robot_state") as sub_robot,
            patch.object(PaintDashboardController, "_subscribe_dashboard_live_view_state") as sub_live_view,
            patch.object(PaintDashboardController, "_unsubscribe_all") as unsub_all,
        ):
            controller = PaintDashboardController(model, view, MagicMock())
            controller.load()

            self.assertTrue(controller._active)
            sub_camera.assert_called_once_with()
            sub_process.assert_called_once_with()
            sub_robot.assert_called_once_with()
            sub_live_view.assert_called_once_with()
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

    def test_status_refresh_updates_even_when_view_reports_not_visible(self) -> None:
        state = DashboardState(process_state="idle")
        model = MagicMock()
        model.load.return_value = state
        view = self._make_view()
        view.isVisible.return_value = False
        with (
            patch.object(PaintDashboardController, "_init_dashboard_camera_feed"),
            patch.object(PaintDashboardController, "_init_dashboard_process_state"),
        ):
            controller = PaintDashboardController(model, view, MagicMock())

        controller._active = True
        controller._refresh_dashboard_status()

        view.apply_dashboard_state.assert_called_once_with(state)

    def test_robot_state_event_refreshes_dashboard_state(self) -> None:
        state = DashboardState(
            process_state="idle",
            card_states={
                1: SimpleNamespace(title="Robot Status", value="IDLE", note="Robot service healthy")
            },
        )
        model = MagicMock()
        model.load.return_value = state
        view = self._make_view()
        with (
            patch.object(PaintDashboardController, "_init_dashboard_camera_feed"),
            patch.object(PaintDashboardController, "_init_dashboard_process_state"),
        ):
            controller = PaintDashboardController(model, view, MagicMock())
        controller._dashboard_process_bridge = MagicMock()

        controller._active = True
        controller._on_dashboard_robot_state_raw(
            SimpleNamespace(
                state="disconnected",
                extra={
                    "last_error": "HTTPConnectionPool: Failed to establish a new connection: Connection refused"
                },
            )
        )

        controller._dashboard_process_bridge.state_ready.emit.assert_called_once_with(state)
        self.assertEqual(state.card_states[1].value, "DISCONNECTED")
        self.assertEqual(state.card_states[1].note, "ROS2 bridge is not reachable")

    def test_robot_state_event_reports_starting_state(self) -> None:
        state = DashboardState(
            process_state="idle",
            card_states={
                1: SimpleNamespace(title="Robot Status", value="IDLE", note="Robot service healthy")
            },
        )
        model = MagicMock()
        model.load.return_value = state
        view = self._make_view()
        with (
            patch.object(PaintDashboardController, "_init_dashboard_camera_feed"),
            patch.object(PaintDashboardController, "_init_dashboard_process_state"),
        ):
            controller = PaintDashboardController(model, view, MagicMock())
        controller._dashboard_process_bridge = MagicMock()

        controller._active = True
        controller._on_dashboard_robot_state_raw(
            SimpleNamespace(
                state="starting",
                extra={"startup": {"message": "ROS runtime is initializing"}},
            )
        )

        controller._dashboard_process_bridge.state_ready.emit.assert_called_once_with(state)
        self.assertEqual(state.card_states[1].value, "STARTING")
        self.assertEqual(state.card_states[1].note, "ROS runtime is initializing")

    def test_subscribe_dashboard_robot_state_uses_robot_state_topic(self) -> None:
        with (
            patch.object(PaintDashboardController, "_init_dashboard_camera_feed"),
            patch.object(PaintDashboardController, "_init_dashboard_process_state"),
        ):
            controller = PaintDashboardController(MagicMock(), self._make_view(), MagicMock())
        controller._subscribe = MagicMock()

        controller._subscribe_dashboard_robot_state()

        controller._subscribe.assert_called_once_with(RobotTopics.STATE, controller._on_dashboard_robot_state_raw)

    def test_subscribe_dashboard_live_view_state_uses_paint_live_view_topic(self) -> None:
        with (
            patch.object(PaintDashboardController, "_init_dashboard_camera_feed"),
            patch.object(PaintDashboardController, "_init_dashboard_process_state"),
        ):
            controller = PaintDashboardController(MagicMock(), self._make_view(), MagicMock())
        controller._subscribe = MagicMock()

        controller._subscribe_dashboard_live_view_state()

        controller._subscribe.assert_called_once_with(
            PaintDashboardLiveViewTopics.STATE,
            controller._on_dashboard_live_view_state_raw,
        )

    def test_dashboard_live_view_state_freezes_capture_frame_and_blocks_live_updates(self) -> None:
        view = self._make_view()
        with (
            patch.object(PaintDashboardController, "_init_dashboard_camera_feed"),
            patch.object(PaintDashboardController, "_init_dashboard_process_state"),
        ):
            controller = PaintDashboardController(MagicMock(), view, MagicMock())
        controller._active = True
        controller._dashboard_camera_bridge = MagicMock()

        controller._on_dashboard_live_view_state_raw(
            PaintDashboardLiveViewEvent(paused=True, image="capture-frame")
        )

        self.assertFalse(controller._dashboard_camera_feed_updates_enabled())
        controller._dashboard_camera_bridge.frame_ready.emit.assert_called_once_with({"image": "capture-frame"})

        controller._on_dashboard_camera_frame_raw({"image": "live-frame"})
        controller._dashboard_camera_bridge.frame_ready.emit.assert_called_once_with({"image": "capture-frame"})

        controller._on_dashboard_live_view_state_raw(PaintDashboardLiveViewEvent(paused=False))

        self.assertTrue(controller._dashboard_camera_feed_updates_enabled())


if __name__ == "__main__":
    unittest.main()

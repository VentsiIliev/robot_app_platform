from __future__ import annotations

from src.applications.base.dashboard_camera_feed_mixin import DashboardCameraFeedMixin
from src.applications.base.dashboard_process_state_mixin import DashboardProcessStateMixin
from src.applications.base.broker_subscription_mixin import BrokerSubscriptionMixin
from src.applications.base.i_application_controller import IApplicationController
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.paint.applications.dashboard.model.paint_dashboard_model import (
    PaintDashboardModel,
)
from src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view import (
    PaintDashboardView,
)


class PaintDashboardController(
    IApplicationController,
    BrokerSubscriptionMixin,
    DashboardCameraFeedMixin,
    DashboardProcessStateMixin,
):
    def __init__(self, model: PaintDashboardModel, view: PaintDashboardView, broker: IMessagingService):
        BrokerSubscriptionMixin.__init__(self)
        self._model = model
        self._view = view
        self._broker = broker
        self._active = False
        self._init_dashboard_camera_feed()
        self._init_dashboard_process_state()
        self._view.start_requested.connect(self._on_start)
        self._view.stop_requested.connect(self._on_stop)
        self._view.pause_requested.connect(self._on_pause)
        self._view.reset_requested.connect(self._on_reset)
        self._view.test_pickup_requested.connect(self._on_test_pickup)
        self._view.go_to_calibration_requested.connect(self._on_go_to_calibration)
        self._view.move_to_calibration_ptp_requested.connect(self._on_move_to_calibration_ptp)
        self._view.move_to_home_zeros_requested.connect(self._on_move_to_home_zeros)
        self._view.pickup_to_paint_position_requested.connect(self._on_pickup_to_paint_position)
        self._view.test_pre_paint_marker_requested.connect(self._on_test_pre_paint_marker)
        self._view.paint_marker_settings_requested.connect(self._on_paint_marker_settings)

    def load(self) -> None:
        self._active = True
        self._subscribe_dashboard_camera_feed()
        self._subscribe_dashboard_process_state()
        self._view.apply_dashboard_state(self._model.load())
        self._view.destroyed.connect(self.stop)

    def stop(self) -> None:
        self._active = False
        self._unsubscribe_all()

    def _on_start(self) -> None:
        self._view.apply_dashboard_state(self._model.start())

    def _on_stop(self) -> None:
        self._view.apply_dashboard_state(self._model.stop_process())

    def _on_pause(self) -> None:
        self._view.apply_dashboard_state(self._model.toggle_pause())

    def _on_reset(self) -> None:
        self._view.apply_dashboard_state(self._model.reset_errors())

    def _on_test_pickup(self) -> None:
        self._model.test_pickup()

    def _on_go_to_calibration(self) -> None:
        self._model.go_to_calibration()

    def _on_move_to_calibration_ptp(self) -> None:
        self._model.move_to_calibration_ptp()

    def _on_move_to_home_zeros(self) -> None:
        self._model.move_to_home_zeros()

    def _on_pickup_to_paint_position(self) -> None:
        self._model.pickup_to_paint_position()

    def _on_test_pre_paint_marker(self) -> None:
        ok, message = self._model.test_pre_paint_marker_position()
        if ok:
            self._view.show_message("Pre-Paint Marker Test", message)
        else:
            self._view.show_error("Pre-Paint Marker Test", message)

    def _on_paint_marker_settings(self) -> None:
        settings = self._model.get_paint_marker_settings()
        updated = self._view.open_paint_marker_settings_dialog(settings)
        if updated is None:
            return
        ok, message = self._model.save_paint_marker_settings(updated)
        if ok:
            self._view.show_message("Pre-Painting Marker Settings", message)
        else:
            self._view.show_error("Pre-Painting Marker Settings", message)

    def _view_ok(self) -> bool:
        if not self._active:
            return False
        try:
            _ = self._view.isVisible()
            return True
        except RuntimeError:
            return False

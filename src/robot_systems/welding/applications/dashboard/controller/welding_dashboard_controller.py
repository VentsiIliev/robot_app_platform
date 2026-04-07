from __future__ import annotations

from src.applications.base.dashboard_camera_feed_mixin import DashboardCameraFeedMixin
from src.applications.base.dashboard_process_state_mixin import DashboardProcessStateMixin
from src.applications.base.broker_subscription_mixin import BrokerSubscriptionMixin
from src.applications.base.i_application_controller import IApplicationController
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.welding.applications.dashboard.model.welding_dashboard_model import (
    WeldingDashboardModel,
)
from src.robot_systems.welding.applications.dashboard.view.welding_dashboard_view import (
    WeldingDashboardView,
)


class WeldingDashboardController(
    IApplicationController,
    BrokerSubscriptionMixin,
    DashboardCameraFeedMixin,
    DashboardProcessStateMixin,
):
    def __init__(self, model: WeldingDashboardModel, view: WeldingDashboardView, broker: IMessagingService):
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

    def _view_ok(self) -> bool:
        if not self._active:
            return False
        try:
            _ = self._view.isVisible()
            return True
        except RuntimeError:
            return False


from __future__ import annotations

from src.applications.base.widget_application import WidgetApplication
from src.robot_systems.twin_robot.applications.choreography_setup.choreography_setup_factory import (
    ChoreographySetupFactory,
)
from src.robot_systems.twin_robot.applications.dashboard.twin_dashboard_factory import (
    TwinDashboardFactory,
)


def _build_dashboard_application(robot_system):
    return WidgetApplication(
        widget_factory=lambda messaging: TwinDashboardFactory().build(
            robot_system._dashboard_service,
            messaging=messaging,
        )
    )


def _build_choreography_setup_application(robot_system):
    return WidgetApplication(
        widget_factory=lambda messaging: ChoreographySetupFactory().build(
            robot_system._choreography_setup_service,
            messaging=messaging,
        )
    )

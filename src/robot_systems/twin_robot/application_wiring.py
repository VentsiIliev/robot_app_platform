from __future__ import annotations


def _build_dashboard_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.twin_robot.applications.dashboard import TwinDashboardFactory

    return WidgetApplication(
        widget_factory=lambda messaging: TwinDashboardFactory().build(
            robot_system._dashboard_service,
            messaging=messaging,
        )
    )


def _build_choreography_setup_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.twin_robot.applications.choreography_setup import ChoreographySetupFactory

    return WidgetApplication(
        widget_factory=lambda messaging: ChoreographySetupFactory().build(
            robot_system._choreography_setup_service,
            messaging=messaging,
        )
    )

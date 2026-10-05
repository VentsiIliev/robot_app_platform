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
def _build_network_settings_application(robot_system):
    from src.applications.network_settings.build_application import build_network_settings_application
    return build_network_settings_application(robot_system)


def _build_software_update_application(robot_system):
    from src.applications.software_update.build_application import build_software_update_application

    def can_schedule():
        # No running-state contract exists for attached twin runtimes yet.
        # Until one is supplied, require an offline CLI update when attached.
        return robot_system._twin_runtime is None

    return build_software_update_application(can_schedule)

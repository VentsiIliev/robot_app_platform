from __future__ import annotations

import os

from src.robot_systems.base_robot_system import BaseRobotSystem
from src.robot_systems.twin_robot import application_wiring
from src.robot_systems.twin_robot.applications.choreography_setup.service.choreography_setup_service import (
    ChoreographySetupService,
)
from src.robot_systems.twin_robot.applications.dashboard.service.twin_dashboard_service import (
    TwinDashboardService,
)
from src.robot_systems.twin_robot.storage import ChoreographyRepository
from src.shared_contracts.declarations import (
    ApplicationSpec,
    FolderSpec,
    RolePolicy,
    ShellSetup,
    SystemMetadata,
)


class TwinRobotSystem(BaseRobotSystem):
    """Platform composition for synchronized two-robot choreography.

    Concrete twin applications live under this robot-system package. The ROS
    transport is injected through ``set_twin_runtime`` so the platform remains
    decoupled from the motion-stack implementation.
    """

    services = []
    settings_specs = []
    movement_groups = []
    work_areas = []

    role_policy = RolePolicy(
        role_values=["Admin", "Operator", "Viewer", "Developer"],
        admin_role_value="Admin",
        default_permission_role_values=["Admin"],
    )

    shell = ShellSetup(
        folders=[
            FolderSpec(folder_id=1, name="PRODUCTION", display_name="Production"),
            FolderSpec(folder_id=2, name="SETUP", display_name="Setup"),
        ],
        applications=[
            ApplicationSpec(
                name="TwinDashboard",
                folder_id=1,
                icon="fa5s.play-circle",
                factory=application_wiring._build_dashboard_application,
            ),
            ApplicationSpec(
                name="ChoreographySetup",
                folder_id=2,
                icon="fa5s.project-diagram",
                factory=application_wiring._build_choreography_setup_application,
            ),
        ],
    )

    metadata = SystemMetadata(
        name="TwinRobotSystem",
        version="0.1.0",
        description="Synchronized twin-robot choreography system",
        author="Platform Team",
        settings_root=os.path.join("storage", "settings"),
    )

    def __init__(self) -> None:
        super().__init__()
        self._twin_runtime = None
        self._choreography_repository = None
        self._dashboard_service = None
        self._choreography_setup_service = None

    def set_twin_runtime(self, runtime) -> None:
        """Attach the transport/runtime adapter used by both twin applications."""
        self._twin_runtime = runtime
        if self._dashboard_service is not None:
            self._dashboard_service.set_runtime(runtime)
        if self._choreography_setup_service is not None:
            self._choreography_setup_service.set_runtime(runtime)

    def on_start(self) -> None:
        choreography_dir = self.storage_path("choreographies")
        self._choreography_repository = ChoreographyRepository(choreography_dir)
        self._dashboard_service = TwinDashboardService(
            self._choreography_repository,
            runtime=self._twin_runtime,
        )
        self._choreography_setup_service = ChoreographySetupService(
            self._choreography_repository,
            runtime=self._twin_runtime,
        )

    def on_stop(self) -> None:
        runtime = self._twin_runtime
        stop = getattr(runtime, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                self._logger.exception("Failed to stop twin runtime")

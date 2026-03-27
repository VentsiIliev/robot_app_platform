from __future__ import annotations

from src.applications.login.login_application_service import LoginApplicationService
from src.applications.login.login_factory import LoginFactory
from src.applications.user_management.domain.auth_user_repository_adapter import AuthUserRepositoryAdapter
from src.applications.user_management.domain.csv_user_repository import CsvUserRepository
from src.engine.auth.authentication_service import AuthenticationService
from src.engine.auth.authorization_service import AuthorizationService
from src.engine.auth.json_permissions_repository import JsonPermissionsRepository
from src.engine.common_service_ids import CommonServiceID
from src.engine.robot.drivers.fairino import FairinoRos2Robot
from src.robot_systems.paint.domain.users import build_paint_user_schema
from src.robot_systems.paint.paint_robot_system import PaintRobotSystem
from src.robot_systems.robot_system_bootstrap_provider import RobotSystemBootstrapProvider


class PaintBootstrapProvider(RobotSystemBootstrapProvider):
    @property
    def system_class(self):
        return PaintRobotSystem

    def build_robot(self):
        # TODO: Move concrete robot driver selection into persisted startup config.
        return FairinoRos2Robot(server_url="http://localhost:5000")

    def build_login_view(self, robot_system, messaging_service):
        role_policy = robot_system.__class__.role_policy
        user_repo = CsvUserRepository(
            robot_system.users_storage_path(),
            build_paint_user_schema(role_policy.role_values),
        )
        auth_service = AuthenticationService(AuthUserRepositoryAdapter(user_repo))
        robot_service = robot_system.get_optional_service(CommonServiceID.ROBOT)
        login_service = LoginApplicationService(
            auth_service=auth_service,
            user_repository=user_repo,
            robot_service=robot_service,
            admin_role_value=role_policy.admin_role_value,
        )
        return LoginFactory.build(login_service, messaging=messaging_service)

    def build_authorization_service(self, robot_system):
        role_policy = robot_system.__class__.role_policy
        return AuthorizationService(
            JsonPermissionsRepository(
                robot_system.permissions_storage_path(),
                default_role_values=role_policy.default_permission_role_values,
            ),
            protected_app_role_values=role_policy.protected_app_role_values,
        )

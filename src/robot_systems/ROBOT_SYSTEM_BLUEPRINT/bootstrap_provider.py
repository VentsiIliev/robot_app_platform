from __future__ import annotations

from src.applications.login.login_application_service import LoginApplicationService
from src.applications.login.login_factory import LoginFactory
from src.applications.user_management.domain.auth_user_repository_adapter import AuthUserRepositoryAdapter
from src.applications.user_management.domain.csv_user_repository import CsvUserRepository
from src.engine.auth.authentication_service import AuthenticationService
from src.engine.auth.authorization_service import AuthorizationService
from src.engine.auth.json_permissions_repository import JsonPermissionsRepository
from src.engine.common_service_ids import CommonServiceID
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.domain.users import build_my_user_schema
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.my_robot_system import MyRobotSystem
from src.robot_systems.robot_system_bootstrap_provider import RobotSystemBootstrapProvider


class MyRobotSystemBootstrapProvider(RobotSystemBootstrapProvider):
    @property
    def system_class(self):
        return MyRobotSystem

    def build_robot(self):
        # TODO: Return the concrete robot driver used by this robot system.
        raise NotImplementedError("TODO: implement build_robot")

    def build_login_view(self, robot_system, messaging_service):
        role_policy = robot_system.__class__.role_policy
        user_repo = CsvUserRepository(
            robot_system.users_storage_path(),
            build_my_user_schema(role_policy.role_values),
        )
        auth_service = AuthenticationService(AuthUserRepositoryAdapter(user_repo))
        robot_service = robot_system.get_optional_service(CommonServiceID.ROBOT)
        login_service = LoginApplicationService(
            auth_service=auth_service,
            user_repository=user_repo,
            robot_service=robot_service,
            admin_role_value=role_policy.admin_role_value,
        )
        # TODO: Replace LoginFactory with a custom login factory only if your
        # robot system needs a different login UI than the shared one.
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

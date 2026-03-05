import sys
import unittest

from src.applications.user_management.service.stub_user_management_service import StubUserManagementService
from src.applications.user_management.user_management_factory import UserManagementFactory
from src.applications.user_management.view.user_management_view import UserManagementView
from src.applications.user_management.controller.user_management_controller import UserManagementController


class TestUserManagementFactory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_build_returns_user_management_view(self):
        result = UserManagementFactory().build(StubUserManagementService())
        self.assertIsInstance(result, UserManagementView)

    def test_build_attaches_controller_to_view(self):
        view = UserManagementFactory().build(StubUserManagementService())
        self.assertIsInstance(view._controller, UserManagementController)

    def test_build_calls_get_all_users_on_load(self):
        from unittest.mock import MagicMock
        from src.applications.user_management.service.i_user_management_service import IUserManagementService
        svc = MagicMock(spec=IUserManagementService)
        svc.get_schema.return_value = StubUserManagementService().get_schema()
        svc.get_all_users.return_value = []
        UserManagementFactory().build(svc)
        svc.get_all_users.assert_called()

    def test_two_builds_produce_independent_views(self):
        v1 = UserManagementFactory().build(StubUserManagementService())
        v2 = UserManagementFactory().build(StubUserManagementService())
        self.assertIsNot(v1, v2)
        self.assertIsNot(v1._controller, v2._controller)

    def test_view_schema_matches_service_schema(self):
        svc = StubUserManagementService()
        view = UserManagementFactory().build(svc)
        self.assertIs(view._schema, svc.get_schema())


if __name__ == "__main__":
    unittest.main()


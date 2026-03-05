import sys
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QDialog

from src.applications.user_management.controller.user_management_controller import UserManagementController
from src.applications.user_management.domain.default_schema import DEFAULT_USER_SCHEMA
from src.applications.user_management.domain.user_schema import UserRecord
from src.applications.user_management.model.user_management_model import UserManagementModel
from src.applications.user_management.view.user_management_view import UserManagementView

_CTRL_MOD = "src.applications.user_management.controller.user_management_controller"


def _record(uid, first="Alice", email="a@b.com"):
    return UserRecord({"id": uid, "firstName": first, "lastName": "Test",
                       "password": "pw", "role": "Admin", "email": email})


def _make_model(records=None):
    model = MagicMock(spec=UserManagementModel)
    model.schema = DEFAULT_USER_SCHEMA
    recs = records or []
    model.load.return_value      = recs
    model.get_users.return_value = recs
    model.add_user.return_value    = (True, "added")
    model.update_user.return_value = (True, "updated")
    model.delete_user.return_value = (True, "deleted")
    model.generate_qr.return_value = (True, "QR generated", "/tmp/qr.png")
    return model


def _make_view():
    return MagicMock(spec=UserManagementView)


def _make_ctrl(records=None):
    model = _make_model(records)
    view  = _make_view()
    ctrl  = UserManagementController(model, view)
    return ctrl, model, view


class TestUserManagementControllerLoad(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_load_connects_all_signals(self):
        ctrl, model, view = _make_ctrl()
        ctrl.load()
        view.add_requested.connect.assert_called()
        view.edit_requested.connect.assert_called()
        view.delete_requested.connect.assert_called()
        view.qr_requested.connect.assert_called()
        view.refresh_requested.connect.assert_called()
        view.filter_changed.connect.assert_called()

    def test_load_calls_refresh(self):
        ctrl, model, view = _make_ctrl()
        ctrl.load()
        view.set_users.assert_called_once()
        view.set_status.assert_called_once()


class TestUserManagementControllerRefresh(unittest.TestCase):

    def test_refresh_loads_from_model_and_sets_view(self):
        records = [_record("1"), _record("2")]
        ctrl, model, view = _make_ctrl(records=records)
        ctrl._refresh()
        view.set_users.assert_called_once_with(records)

    def test_refresh_status_includes_count(self):
        records = [_record("1"), _record("2"), _record("3")]
        ctrl, model, view = _make_ctrl(records=records)
        ctrl._refresh()
        msg = view.set_status.call_args[0][0]
        self.assertIn("3", msg)


class TestUserManagementControllerOnAdd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    @patch(f"{_CTRL_MOD}._UserDialog")
    def test_rejected_dialog_does_not_call_model(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Rejected
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        ctrl._on_add()
        model.add_user.assert_not_called()

    @patch(f"{_CTRL_MOD}._UserDialog")
    def test_accepted_calls_add_user(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_record.return_value = _record("99")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        ctrl._on_add()
        model.add_user.assert_called_once()

    @patch(f"{_CTRL_MOD}._UserDialog")
    def test_success_refreshes_view(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_record.return_value = _record("99")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        ctrl._on_add()
        view.set_users.assert_called()

    @patch(f"{_CTRL_MOD}.show_warning")
    @patch(f"{_CTRL_MOD}._UserDialog")
    def test_failure_shows_warning(self, MockDialog, mock_warn):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_record.return_value = _record("1")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        model.add_user.return_value = (False, "already exists")
        ctrl._on_add()
        mock_warn.assert_called_once()

    @patch(f"{_CTRL_MOD}.show_warning")
    @patch(f"{_CTRL_MOD}._UserDialog")
    def test_value_error_shows_invalid_input_warning(self, MockDialog, mock_warn):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_record.side_effect = ValueError("ID is required")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        ctrl._on_add()
        mock_warn.assert_called_once()
        self.assertIn("Invalid", mock_warn.call_args[0][1])


class TestUserManagementControllerOnEdit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    @patch(f"{_CTRL_MOD}._UserDialog")
    def test_rejected_dialog_does_not_call_model(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Rejected
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        ctrl._on_edit(_record("1"))
        model.update_user.assert_not_called()

    @patch(f"{_CTRL_MOD}._UserDialog")
    def test_accepted_calls_update_user(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_record.return_value = _record("1", first="Updated")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        ctrl._on_edit(_record("1"))
        model.update_user.assert_called_once()

    @patch(f"{_CTRL_MOD}.show_warning")
    @patch(f"{_CTRL_MOD}._UserDialog")
    def test_failure_shows_warning(self, MockDialog, mock_warn):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_record.return_value = _record("1")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        model.update_user.return_value = (False, "not found")
        ctrl._on_edit(_record("1"))
        mock_warn.assert_called_once()

    @patch(f"{_CTRL_MOD}.show_warning")
    @patch(f"{_CTRL_MOD}._UserDialog")
    def test_value_error_shows_warning(self, MockDialog, mock_warn):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_record.side_effect = ValueError("bad data")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        ctrl._on_edit(_record("1"))
        mock_warn.assert_called_once()


class TestUserManagementControllerOnDelete(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    @patch(f"{_CTRL_MOD}.ask_yes_no")
    def test_cancelled_does_not_call_model(self, mock_ask):
        mock_ask.return_value = False
        ctrl, model, view = _make_ctrl()
        ctrl._on_delete(_record("1"))
        model.delete_user.assert_not_called()

    @patch(f"{_CTRL_MOD}.ask_yes_no")
    def test_confirmed_calls_delete_user(self, mock_ask):
        mock_ask.return_value = True
        ctrl, model, view = _make_ctrl()
        ctrl._on_delete(_record("1"))
        model.delete_user.assert_called_once_with("1")

    @patch(f"{_CTRL_MOD}.ask_yes_no")
    def test_success_refreshes_view(self, mock_ask):
        mock_ask.return_value = True
        ctrl, model, view = _make_ctrl()
        ctrl._on_delete(_record("1"))
        view.set_users.assert_called()

    @patch(f"{_CTRL_MOD}.ask_yes_no")
    def test_failure_sets_status_only(self, mock_ask):
        mock_ask.return_value = True
        ctrl, model, view = _make_ctrl()
        model.delete_user.return_value = (False, "not found")
        ctrl._on_delete(_record("1"))
        view.set_users.assert_not_called()
        view.set_status.assert_called()


class TestUserManagementControllerOnQr(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    @patch(f"{_CTRL_MOD}.show_warning")
    def test_generate_qr_failure_shows_warning(self, mock_warn):
        ctrl, model, view = _make_ctrl()
        model.generate_qr.return_value = (False, "error", None)
        ctrl._on_qr(_record("1"))
        mock_warn.assert_called_once()

    @patch(f"{_CTRL_MOD}._QrDialog")
    def test_generate_qr_success_opens_dialog(self, MockDialog):
        mock_dlg = MagicMock()
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        model.generate_qr.return_value = (True, "ok", "/tmp/qr.png")
        ctrl._on_qr(_record("1"))
        MockDialog.assert_called_once()
        mock_dlg.exec.assert_called_once()


class TestUserManagementControllerOnFilter(unittest.TestCase):

    def test_empty_value_shows_all_records(self):
        records = [_record("1", first="Alice"), _record("2", first="Bob")]
        ctrl, model, view = _make_ctrl(records=records)
        ctrl._on_filter("First Name", "")
        view.set_users.assert_called_with(records)

    def test_all_column_shows_all_records(self):
        records = [_record("1"), _record("2")]
        ctrl, model, view = _make_ctrl(records=records)
        ctrl._on_filter("All", "alice")
        view.set_users.assert_called_with(records)

    def test_filter_by_first_name_returns_matching(self):
        r1 = _record("1", first="Alice")
        r2 = _record("2", first="Bob")
        ctrl, model, view = _make_ctrl(records=[r1, r2])
        ctrl._on_filter("First Name", "ali")
        filtered = view.set_users.call_args[0][0]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].get("firstName"), "Alice")

    def test_filter_masked_field_shows_all(self):
        records = [_record("1"), _record("2")]
        ctrl, model, view = _make_ctrl(records=records)
        # "Password" is mask_in_table=True — fd will be None → show all
        ctrl._on_filter("Password", "pw")
        view.set_users.assert_called_with(records)

    def test_filter_status_shows_match_counts(self):
        r1 = _record("1", first="Alice")
        r2 = _record("2", first="Bob")
        ctrl, model, view = _make_ctrl(records=[r1, r2])
        ctrl._on_filter("First Name", "ali")
        msg = view.set_status.call_args[0][0]
        self.assertIn("1", msg)
        self.assertIn("2", msg)


if __name__ == "__main__":
    unittest.main()


import sys
import unittest

from PyQt6.QtCore import Qt

from src.applications.user_management.domain.default_schema import DEFAULT_USER_SCHEMA
from src.applications.user_management.domain.user_schema import UserRecord
from src.applications.user_management.view.user_management_view import UserManagementView


def _record(uid, first="Alice", last="Test", role="Admin", email="a@b.com"):
    return UserRecord({"id": uid, "firstName": first, "lastName": last,
                       "password": "secret", "role": role, "email": email})


class TestUserManagementViewSetUsers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)
        cls._view = UserManagementView(schema=DEFAULT_USER_SCHEMA)

    def test_set_users_populates_rows(self):
        self._view.set_users([_record("1"), _record("2")])
        self.assertEqual(self._view._table.rowCount(), 2)

    def test_set_users_replaces_previous_rows(self):
        self._view.set_users([_record("1"), _record("2"), _record("3")])
        self._view.set_users([_record("4")])
        self.assertEqual(self._view._table.rowCount(), 1)

    def test_set_users_empty_clears_table(self):
        self._view.set_users([_record("1")])
        self._view.set_users([])
        self.assertEqual(self._view._table.rowCount(), 0)

    def test_set_users_masks_password_column(self):
        self._view.set_users([_record("1")])
        # Password column index in DEFAULT_USER_SCHEMA table fields
        headers = DEFAULT_USER_SCHEMA.get_table_headers()
        pwd_col = headers.index("Password")
        item = self._view._table.item(0, pwd_col)
        self.assertEqual(item.text(), "****")

    def test_set_users_stores_record_in_user_role(self):
        record = _record("42")
        self._view.set_users([record])
        stored = self._view._table.item(0, 0).data(Qt.ItemDataRole.UserRole)
        self.assertEqual(stored.get("id"), "42")


class TestUserManagementViewSetStatus(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)
        cls._view = UserManagementView(schema=DEFAULT_USER_SCHEMA)

    def test_set_status_updates_label(self):
        self._view.set_status("5 users loaded")
        self.assertEqual(self._view._status.text(), "5 users loaded")

    def test_set_status_empty(self):
        self._view.set_status("")
        self.assertEqual(self._view._status.text(), "")


class TestUserManagementViewSelectedRecord(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._view = UserManagementView(schema=DEFAULT_USER_SCHEMA)

    def test_selected_record_returns_none_when_no_selection(self):
        self._view.set_users([_record("1")])
        self.assertIsNone(self._view.selected_record())

    def test_selected_record_returns_record_after_selection(self):
        self._view.set_users([_record("7", first="Bob")])
        self._view._table.selectRow(0)
        record = self._view.selected_record()
        self.assertIsNotNone(record)
        self.assertEqual(record.get("id"), "7")
        self.assertEqual(record.get("firstName"), "Bob")


class TestUserManagementViewButtonStates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._view = UserManagementView(schema=DEFAULT_USER_SCHEMA)

    def test_edit_delete_qr_buttons_disabled_initially(self):
        self.assertFalse(self._view._btn_edit.isEnabled())
        self.assertFalse(self._view._btn_delete.isEnabled())
        self.assertFalse(self._view._btn_qr.isEnabled())

    def test_buttons_enabled_after_row_selection(self):
        self._view.set_users([_record("1")])
        self._view._table.selectRow(0)
        self.assertTrue(self._view._btn_edit.isEnabled())
        self.assertTrue(self._view._btn_delete.isEnabled())
        self.assertTrue(self._view._btn_qr.isEnabled())

    def test_buttons_disabled_after_table_cleared(self):
        self._view.set_users([_record("1")])
        self._view._table.selectRow(0)
        self._view.set_users([])  # clears rows → currentRow() returns -1
        self.assertFalse(self._view._btn_edit.isEnabled())
        self.assertFalse(self._view._btn_delete.isEnabled())
        self.assertFalse(self._view._btn_qr.isEnabled())


class TestUserManagementViewSignals(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._view = UserManagementView(schema=DEFAULT_USER_SCHEMA)

    def test_add_button_emits_add_requested(self):
        received = []
        self._view.add_requested.connect(lambda: received.append(True))
        self._view._btn_add.click()
        self.assertTrue(received)

    def test_refresh_button_emits_refresh_requested(self):
        received = []
        self._view.refresh_requested.connect(lambda: received.append(True))
        self._view._btn_refresh.click()
        self.assertTrue(received)

    def test_edit_button_emits_edit_requested_with_record(self):
        received = []
        self._view.edit_requested.connect(lambda r: received.append(r))
        self._view.set_users([_record("5", first="Eve")])
        self._view._table.selectRow(0)
        self._view._btn_edit.click()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].get("id"), "5")

    def test_delete_button_emits_delete_requested_with_record(self):
        received = []
        self._view.delete_requested.connect(lambda r: received.append(r))
        self._view.set_users([_record("3")])
        self._view._table.selectRow(0)
        self._view._btn_delete.click()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].get("id"), "3")

    def test_qr_button_emits_qr_requested_with_record(self):
        received = []
        self._view.qr_requested.connect(lambda r: received.append(r))
        self._view.set_users([_record("9")])
        self._view._table.selectRow(0)
        self._view._btn_qr.click()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].get("id"), "9")

    def test_filter_button_emits_filter_changed(self):
        received = []
        self._view.filter_changed.connect(lambda col, val: received.append((col, val)))
        self._view._filter_input.setText("alice")
        self._view._filter_col.setCurrentIndex(1)  # First non-"All" column
        # Click the Filter button
        from PyQt6.QtWidgets import QPushButton
        btns = self._view.findChildren(QPushButton)
        filter_btn = next((b for b in btns if b.text() == "Filter"), None)
        if filter_btn:
            filter_btn.click()
        self.assertTrue(len(received) > 0)

    def test_clear_button_resets_filter_and_emits_all(self):
        received = []
        self._view.filter_changed.connect(lambda col, val: received.append((col, val)))
        self._view._filter_input.setText("something")
        from PyQt6.QtWidgets import QPushButton
        btns = self._view.findChildren(QPushButton)
        clear_btn = next((b for b in btns if b.text() == "Clear"), None)
        if clear_btn:
            clear_btn.click()
        self.assertEqual(self._view._filter_input.text(), "")
        self.assertTrue(any(col == "All" for col, _ in received))

    def test_clean_up_does_not_raise(self):
        self._view.clean_up()


if __name__ == "__main__":
    unittest.main()


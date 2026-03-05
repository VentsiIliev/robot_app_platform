import unittest

from src.applications.user_management.domain.user import User, Role, UserField
from src.applications.user_management.domain.user_schema import (
    UserRecord, FieldDescriptor,
)
from src.applications.user_management.domain.default_schema import DEFAULT_USER_SCHEMA


class TestUserRecord(unittest.TestCase):

    def _make(self, **kw):
        data = {"id": "1", "firstName": "Alice", "lastName": "A", "role": "Admin"}
        data.update(kw)
        return UserRecord(data)

    def test_get_returns_value(self):
        r = self._make(firstName="Bob")
        self.assertEqual(r.get("firstName"), "Bob")

    def test_get_returns_default_for_missing(self):
        r = self._make()
        self.assertIsNone(r.get("nonexistent"))

    def test_get_returns_explicit_default(self):
        r = self._make()
        self.assertEqual(r.get("nonexistent", "fallback"), "fallback")

    def test_set_updates_value(self):
        r = self._make(firstName="Alice")
        r.set("firstName", "Bob")
        self.assertEqual(r.get("firstName"), "Bob")

    def test_get_id_returns_id_key_value(self):
        r = self._make()
        self.assertEqual(r.get_id("id"), "1")

    def test_to_dict_returns_copy(self):
        r = self._make(firstName="Alice")
        d = r.to_dict()
        self.assertEqual(d["firstName"], "Alice")

    def test_to_dict_is_independent_copy(self):
        r = self._make()
        d = r.to_dict()
        d["id"] = "99"
        self.assertNotEqual(r.get("id"), "99")

    def test_from_dict_round_trips(self):
        data = {"id": "1", "firstName": "Alice", "lastName": "A", "role": "Admin"}
        r = UserRecord.from_dict(data)
        self.assertEqual(r.get("firstName"), "Alice")

    def test_repr_contains_data(self):
        r = self._make()
        self.assertIn("Alice", repr(r))


class TestUserSchema(unittest.TestCase):

    def setUp(self):
        self._schema = DEFAULT_USER_SCHEMA

    def test_get_table_fields_returns_visible_fields(self):
        fields = self._schema.get_table_fields()
        self.assertTrue(all(f.table_display for f in fields))

    def test_get_table_headers_returns_labels(self):
        headers = self._schema.get_table_headers()
        self.assertIn("ID", headers)
        self.assertIn("First Name", headers)

    def test_get_filterable_labels_starts_with_all(self):
        labels = self._schema.get_filterable_labels()
        self.assertEqual(labels[0], "All")

    def test_get_filterable_labels_excludes_masked(self):
        labels = self._schema.get_filterable_labels()
        self.assertNotIn("Password", labels)

    def test_get_filterable_labels_includes_non_masked(self):
        labels = self._schema.get_filterable_labels()
        self.assertIn("First Name", labels)


class TestFieldDescriptor(unittest.TestCase):

    def test_defaults(self):
        fd = FieldDescriptor(key="name", label="Name", widget="text")
        self.assertTrue(fd.required)
        self.assertTrue(fd.table_display)
        self.assertFalse(fd.read_only_on_edit)
        self.assertFalse(fd.mask_in_table)
        self.assertIsNone(fd.options)

    def test_combo_with_options(self):
        fd = FieldDescriptor(key="role", label="Role", widget="combo", options=["A", "B"])
        self.assertEqual(fd.options, ["A", "B"])

    def test_mask_in_table(self):
        fd = FieldDescriptor(key="pwd", label="Password", widget="password", mask_in_table=True)
        self.assertTrue(fd.mask_in_table)


class TestUser(unittest.TestCase):

    def _make(self, **kw):
        defaults = dict(id=1, firstName="Alice", lastName="Smith", password="pw", role=Role.ADMIN)
        defaults.update(kw)
        return User(**defaults)

    def test_get_full_name(self):
        u = self._make(firstName="Alice", lastName="Smith")
        self.assertEqual(u.get_full_name(), "Alice Smith")

    def test_to_dict_contains_all_fields(self):
        u = self._make()
        d = u.to_dict()
        self.assertIn("id", d)
        self.assertIn("firstName", d)
        self.assertIn("role", d)

    def test_to_dict_role_is_value(self):
        u = self._make(role=Role.OPERATOR)
        self.assertEqual(u.to_dict()["role"], "Operator")

    def test_from_dict_creates_user(self):
        d = {"id": 2, "firstName": "Bob", "lastName": "B", "password": "pw", "role": "Operator"}
        u = User.from_dict(d)
        self.assertEqual(u.firstName, "Bob")
        self.assertEqual(u.role, Role.OPERATOR)

    def test_from_dict_invalid_role_defaults_operator(self):
        d = {"id": 1, "firstName": "X", "lastName": "Y", "password": "p", "role": "Unknown"}
        u = User.from_dict(d)
        self.assertEqual(u.role, Role.OPERATOR)

    def test_from_dict_email_none_when_empty(self):
        d = {"id": 1, "firstName": "X", "lastName": "Y", "password": "p", "role": "Admin", "email": ""}
        u = User.from_dict(d)
        self.assertIsNone(u.email)

    def test_from_dict_email_set_when_present(self):
        d = {"id": 1, "firstName": "X", "lastName": "Y", "password": "p", "role": "Admin", "email": "x@x.com"}
        u = User.from_dict(d)
        self.assertEqual(u.email, "x@x.com")


class TestRoleEnum(unittest.TestCase):

    def test_admin_value(self):
        self.assertEqual(Role.ADMIN.value, "Admin")

    def test_operator_value(self):
        self.assertEqual(Role.OPERATOR.value, "Operator")

    def test_viewer_value(self):
        self.assertEqual(Role.VIEWER.value, "Viewer")


class TestUserFieldEnum(unittest.TestCase):

    def test_id_value(self):
        self.assertEqual(UserField.ID.value, "id")

    def test_first_name_value(self):
        self.assertEqual(UserField.FIRST_NAME.value, "firstName")

    def test_password_value(self):
        self.assertEqual(UserField.PASSWORD.value, "password")


if __name__ == "__main__":
    unittest.main()


"""
Tests for src/engine/auth/i_authenticated_user.py
"""
import unittest
from enum import Enum

from src.engine.auth.i_authenticated_user import IAuthenticatedUser


class _DummyRole(Enum):
    ADMIN = "Admin"
    OPERATOR = "Operator"


class _ConcreteUser(IAuthenticatedUser):
    @property
    def user_id(self) -> str:
        return "42"

    @property
    def role(self) -> Enum:
        return _DummyRole.ADMIN


class TestIAuthenticatedUser(unittest.TestCase):

    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            IAuthenticatedUser()

    def test_concrete_subclass_instantiates(self):
        user = _ConcreteUser()
        self.assertIsNotNone(user)

    def test_user_id_returns_string(self):
        user = _ConcreteUser()
        self.assertIsInstance(user.user_id, str)
        self.assertEqual(user.user_id, "42")

    def test_role_returns_enum(self):
        user = _ConcreteUser()
        self.assertIsInstance(user.role, Enum)
        self.assertEqual(user.role, _DummyRole.ADMIN)

    def test_role_value_is_accessible(self):
        user = _ConcreteUser()
        self.assertEqual(user.role.value, "Admin")

    def test_missing_user_id_raises_on_instantiation(self):
        class _MissingUserId(IAuthenticatedUser):
            @property
            def role(self) -> Enum:
                return _DummyRole.ADMIN

        with self.assertRaises(TypeError):
            _MissingUserId()

    def test_missing_role_raises_on_instantiation(self):
        class _MissingRole(IAuthenticatedUser):
            @property
            def user_id(self) -> str:
                return "1"

        with self.assertRaises(TypeError):
            _MissingRole()


if __name__ == "__main__":
    unittest.main()

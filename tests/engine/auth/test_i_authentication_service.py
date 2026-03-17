"""
Tests for src/engine/auth/i_authentication_service.py

Verifies the interface contract using a minimal stub.
"""
import unittest
from enum import Enum
from unittest.mock import MagicMock

from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_authentication_service import IAuthenticationService


class _DummyUser(IAuthenticatedUser):
    @property
    def user_id(self) -> str:
        return "1"

    @property
    def role(self) -> Enum:
        from enum import Enum
        class R(Enum):
            ADMIN = "Admin"
        return R.ADMIN


class _StubAuthenticationService(IAuthenticationService):
    def authenticate(self, user_id: str, password: str):
        return _DummyUser() if user_id == "1" and password == "secret" else None

    def authenticate_qr(self, qr_payload: str):
        return _DummyUser() if qr_payload == "valid" else None


class TestIAuthenticationService(unittest.TestCase):

    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            IAuthenticationService()

    def test_stub_satisfies_interface(self):
        svc = _StubAuthenticationService()
        self.assertIsInstance(svc, IAuthenticationService)

    def test_authenticate_returns_user_on_valid_credentials(self):
        svc = _StubAuthenticationService()
        result = svc.authenticate("1", "secret")
        self.assertIsInstance(result, IAuthenticatedUser)

    def test_authenticate_returns_none_on_invalid_credentials(self):
        svc = _StubAuthenticationService()
        self.assertIsNone(svc.authenticate("1", "wrong"))

    def test_authenticate_qr_returns_user_on_valid_payload(self):
        svc = _StubAuthenticationService()
        result = svc.authenticate_qr("valid")
        self.assertIsInstance(result, IAuthenticatedUser)

    def test_authenticate_qr_returns_none_on_invalid_payload(self):
        svc = _StubAuthenticationService()
        self.assertIsNone(svc.authenticate_qr("bad"))


if __name__ == "__main__":
    unittest.main()

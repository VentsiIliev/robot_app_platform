from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class AuthUserRecord:
    """Minimal auth-facing user record.

    This stays intentionally narrow so authentication can be reused across
    robot systems regardless of the underlying user storage implementation.
    """

    user_id: str
    password: str
    role: Enum
    payload: dict[str, Any] = field(default_factory=dict)

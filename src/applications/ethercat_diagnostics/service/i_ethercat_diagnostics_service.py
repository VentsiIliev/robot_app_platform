from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EthercatSlaveStatus:
    slave_id: int | str
    name: str = ""
    state: str = "unknown"
    online: bool | None = None
    operational: bool | None = None
    error: str = ""
    statusword: int | str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EthercatDiagnosticsSnapshot:
    master_state: str = "unknown"
    master_message: str = ""
    slaves: tuple[EthercatSlaveStatus, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


class IEthercatDiagnosticsService(ABC):
    """Generic EtherCAT diagnostics contract, independent of a concrete master."""

    @abstractmethod
    def refresh(self) -> EthercatDiagnosticsSnapshot: ...

    def supports_reset_errors(self) -> bool:
        return False

    def reset_errors(self) -> tuple[bool, str]:
        return False, "Reset is not supported by this EtherCAT diagnostics provider"

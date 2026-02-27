from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GeneratorState:
    is_on:                bool              = False
    is_healthy:           bool              = False
    communication_errors: List[str]         = field(default_factory=list)
    elapsed_seconds:      Optional[float]   = None

    @property
    def has_errors(self) -> bool:
        return bool(self.communication_errors)

    def __str__(self) -> str:
        return (
            f"Generator [{'ON' if self.is_on else 'OFF'}]"
            f" [{'healthy' if self.is_healthy else 'unhealthy'}]"
            + (f" elapsed={self.elapsed_seconds:.1f}s" if self.elapsed_seconds is not None else "")
        )
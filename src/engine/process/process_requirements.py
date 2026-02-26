from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, FrozenSet, List


@dataclass(frozen=True)
class ProcessRequirements:
    services: FrozenSet[str] = field(default_factory=frozenset)

    @classmethod
    def requires(cls, *service_names: str) -> ProcessRequirements:
        return cls(services=frozenset(service_names))

    @classmethod
    def none(cls) -> ProcessRequirements:
        return cls(services=frozenset())

    def missing_from(self, checker: Callable[[str], bool]) -> List[str]:
        return [s for s in sorted(self.services) if not checker(s)]

    def all_available(self, checker: Callable[[str], bool]) -> bool:
        return not self.missing_from(checker)

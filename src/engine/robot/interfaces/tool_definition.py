from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolDefinition:
    id:   int
    name: str
    reference_tool_id: Optional[int] = None
    relative_transform: list[float] = field(
        default_factory=lambda: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    )
    collision_profile: str = ""

    def __post_init__(self) -> None:
        values = [float(value) for value in self.relative_transform]
        if len(values) != 6:
            raise ValueError("relative_transform must contain [x, y, z, rx, ry, rz]")
        self.relative_transform = values

    def __str__(self) -> str:
        return self.name

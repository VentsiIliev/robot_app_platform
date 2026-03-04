from dataclasses import dataclass


@dataclass
class ToolDefinition:
    id:   int
    name: str

    def __str__(self) -> str:
        return self.name
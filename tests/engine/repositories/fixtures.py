from enum import Enum


class SettingsIDTestEnum(str, Enum):
    A = "a"
    B = "b"
    C = "c"

    def __str__(self) -> str:
        return self.value

    def __format__(self, spec: str) -> str:
        return self.value.__format__(spec)
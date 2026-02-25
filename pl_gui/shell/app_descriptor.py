from dataclasses import dataclass


@dataclass
class AppDescriptor:
    name: str
    icon_str: str  # QtAwesome icon string like 'fa5s.tachometer-alt'
    folder_id: int

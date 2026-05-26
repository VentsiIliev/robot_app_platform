from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SettingsGroup:
    title: str
    keys: List[str]


@dataclass
class SettingsConfig:
    default_settings: Dict[str, str]
    groups: List[SettingsGroup]
    combo_field_key: str = ""


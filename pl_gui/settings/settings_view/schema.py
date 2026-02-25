from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class SettingField:
    key: str           # signal key, unique across the tab
    label: str         # display text
    widget_type: str   # 'spinbox' | 'double_spinbox' | 'line_edit' | 'combo' | 'toggle'
    default: Any = None
    min_val: float = 0
    max_val: float = 100
    step: float = 1.0
    decimals: int = 2
    suffix: str = ""
    choices: Optional[List[str]] = None   # required when widget_type='combo'
    step_options: Optional[List[float]] = None  # touch step sizes, e.g. [1, 5, 10]


@dataclass
class SettingGroup:
    title: str
    fields: List[SettingField] = field(default_factory=list)

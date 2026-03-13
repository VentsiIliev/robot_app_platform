from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SegmentSettingSpec:
    key:       str
    label:     str
    default:   str
    group:     str              # panel group name, e.g. "General"
    validator: str = "numeric"  # "numeric" | "combo" | "any"


@dataclass
class SegmentSettingsSchema:
    fields:        List[SegmentSettingSpec]
    combo_key:     str         # which field drives the combo/dropdown in the settings panel
    combo_options: List[str]   # available options for that combo

    def get_defaults(self) -> Dict[str, str]:
        defaults = {f.key: f.default for f in self.fields}
        if self.combo_key and self.combo_options and not defaults.get(self.combo_key):
            defaults[self.combo_key] = self.combo_options[0]
        return defaults

    def get_groups(self) -> Dict[str, List[str]]:
        groups: Dict[str, List[str]] = {}
        for f in self.fields:
            groups.setdefault(f.group, []).append(f.key)
        return groups

    def get_label(self, key: str) -> str:
        spec = self._get(key)
        return spec.label if spec else key.replace("_", " ").title()

    def validate(self, key: str, value: str) -> bool:
        spec = self._get(key)
        if spec is None or not value or not value.strip():
            return False
        if spec.validator == "combo":
            return bool(value)
        if spec.validator == "any":
            return True
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def _get(self, key: str) -> Optional[SegmentSettingSpec]:
        return next((f for f in self.fields if f.key == key), None)

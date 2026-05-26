from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LayerRoleConfig:
    role: str
    name: str
    color: str
    visible: bool = True
    enabled: bool = True


@dataclass
class ContourEditorLayerConfig:
    roles: dict[str, LayerRoleConfig] = field(default_factory=dict)
    default_segment_role: str = "contour"

    @classmethod
    def default(cls) -> "ContourEditorLayerConfig":
        return cls(
            roles={
                "workpiece": LayerRoleConfig("workpiece", "Main", "#FF0000", visible=True, enabled=True),
                "contour": LayerRoleConfig("contour", "Contour", "#00FFFF", visible=True, enabled=True),
                "fill": LayerRoleConfig("fill", "Fill", "#00FF00", visible=True, enabled=True),
            },
            default_segment_role="contour",
        )

    def role(self, role_name: str) -> LayerRoleConfig:
        return self.roles[role_name]

    def name_for_role(self, role_name: str) -> str:
        return self.role(role_name).name

    def enabled_roles(self) -> list[LayerRoleConfig]:
        return [cfg for cfg in self.roles.values() if cfg.enabled]

    def enabled_layer_names(self) -> list[str]:
        return [cfg.name for cfg in self.enabled_roles()]

    def color_map(self) -> dict[str, str]:
        return {cfg.name: cfg.color for cfg in self.enabled_roles()}

    def role_for_name(self, layer_name: str) -> str | None:
        for role_name, cfg in self.roles.items():
            if cfg.name == layer_name:
                return role_name
        return None

    def is_fill_layer_name(self, layer_name: str) -> bool:
        return self.role_for_name(layer_name) == "fill"

    def is_enabled(self, role_name: str) -> bool:
        cfg = self.roles.get(role_name)
        return bool(cfg and cfg.enabled)

    def default_segment_layer_name(self) -> str:
        if self.is_enabled(self.default_segment_role):
            return self.name_for_role(self.default_segment_role)
        enabled = self.enabled_layer_names()
        if not enabled:
            raise ValueError("ContourEditorLayerConfig has no enabled layers")
        return enabled[0]

    def pattern_layer_names(self) -> list[str]:
        result: list[str] = []
        for role_name in ("contour", "fill"):
            if self.is_enabled(role_name):
                result.append(self.name_for_role(role_name))
        return result

    def main_contour_layer_names(self) -> list[str]:
        result: list[str] = []
        for role_name in ("workpiece", "contour", "fill"):
            if self.is_enabled(role_name):
                result.append(self.name_for_role(role_name))
        return result

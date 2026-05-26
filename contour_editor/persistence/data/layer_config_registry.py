from __future__ import annotations

from ..config.layer_config import ContourEditorLayerConfig


class LayerConfigRegistry:
    _instance = None
    _config: ContourEditorLayerConfig | None = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_config(self, config: ContourEditorLayerConfig):
        if not isinstance(config, ContourEditorLayerConfig):
            raise TypeError("config must be a ContourEditorLayerConfig")
        self._config = config
        from ..config.constants import set_layer_colors

        set_layer_colors(config.color_map())

    def get_config(self) -> ContourEditorLayerConfig:
        if self._config is None:
            self._config = ContourEditorLayerConfig.default()
            from ..config.constants import set_layer_colors

            set_layer_colors(self._config.color_map())
        return self._config

    def reset(self):
        self._config = None

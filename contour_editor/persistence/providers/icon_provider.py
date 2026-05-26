import os
from typing import Optional, Protocol
from PyQt6.QtGui import QIcon, QPixmap


class IIconProvider(Protocol):
    def get_icon(self, name: str) -> QIcon:
        ...


class DefaultIconProvider:
    def __init__(self):
        # Icons are at src/contour_editor/assets/icons
        # This file is at src/contour_editor/api/providers/icon_provider.py
        # So we need to go up 2 levels (to contour_editor), then into assets/icons
        provider_dir = os.path.dirname(__file__)
        contour_editor_dir = os.path.dirname(os.path.dirname(provider_dir))
        self.icons_dir = os.path.join(contour_editor_dir, 'assets', 'icons')
        print(f"Resource directory: {self.icons_dir}")

    def get_icon(self, name: str) -> QIcon:
        icon_path = os.path.join(self.icons_dir, f"{name}.png")
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        print(f"Warning: Icon not found: {icon_path}")
        return QIcon()


class IconProvider:
    _instance = None
    _provider: IIconProvider = None

    @classmethod
    def get(cls) -> 'IconProvider':
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._provider = DefaultIconProvider()
        return cls._instance

    def set_custom_provider(self, provider: IIconProvider):
        self._provider = provider
        print(f"[IconProvider] Using custom provider: {provider.__class__.__name__}")

    def get_icon(self, name: str) -> QIcon:
        return self._provider.get_icon(name)

    def reset(self):
        self._provider = DefaultIconProvider()


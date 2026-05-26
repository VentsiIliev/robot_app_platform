"""
Settings Provider Singleton

Manages the settings provider instance for the ContourEditor.
Allows applications to inject their own settings definitions.
"""

from typing import Optional
from ...models.interfaces.interfaces import ISettingsProvider


class SettingsProviderRegistry:
    """
    Singleton registry for settings provider.

    Allows applications to inject custom settings definitions while
    providing a sensible fallback.

    Usage:
        # In application initialization:
        from frontend.contour_editor.settings_provider_registry import SettingsProviderRegistry
        from my_app.settings import MySettingsProvider

        registry = SettingsProviderRegistry.get_instance()
        registry.set_provider(MySettingsProvider())

        # In ContourEditor:
        provider = SettingsProviderRegistry.get_instance().get_provider()
        default_values = provider.get_default_values()
    """

    _instance = None
    _provider: Optional[ISettingsProvider] = None

    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_provider(self, provider: ISettingsProvider):
        """
        Set the settings provider to use.

        Args:
            provider: Instance implementing ISettingsProvider interface
        """
        if not isinstance(provider, ISettingsProvider):
            raise TypeError(f"Provider must implement ISettingsProvider interface")

        self._provider = provider
        print(f"[SettingsProviderRegistry] Using custom provider: {provider.__class__.__name__}")

    def get_provider(self) -> ISettingsProvider:
        """
        Get the current settings provider.

        Returns:
            Settings provider instance (raises error if not set)
        """
        if self._provider is None:
            raise RuntimeError(
                "No settings provider registered! "
                "Application must call SettingsProviderRegistry.get_instance().set_provider(provider) "
                "before using ContourEditor."
            )
        return self._provider

    def has_provider(self) -> bool:
        """Check if a provider is registered"""
        return self._provider is not None

    def reset(self):
        """Reset to no provider (useful for testing)"""
        self._provider = None


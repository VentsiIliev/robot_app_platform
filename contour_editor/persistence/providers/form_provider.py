from typing import Optional, Protocol, Callable
from PyQt6.QtWidgets import QWidget


class IAdditionalFormFactory(Protocol):
    """Protocol for creating additional data forms"""

    def create_form(self, parent: Optional[QWidget] = None) -> QWidget:
        """
        Create an additional data form instance.

        Args:
            parent: Parent widget

        Returns:
            Widget instance that implements the additional form interface
        """
        ...


class AdditionalFormProvider:
    """
    Singleton provider for additional data form factory.

    Allows applications to inject custom additional data form implementations
    into the contour editor.

    Usage in plugin:
        from frontend.contour_editor import AdditionalFormProvider
        from frontend.forms.CustomDataForm import CustomDataForm

        class CustomFormFactory:
            def create_form(self, parent=None):
                form = CustomDataForm(parent=parent)
                form.setFixedWidth(400)
                return form

        AdditionalFormProvider.get().set_factory(CustomFormFactory())

    Usage in ContourEditor:
        form = AdditionalFormProvider.get().create_form(self)
    """

    _instance = None
    _factory: Optional[IAdditionalFormFactory] = None

    @classmethod
    def get(cls) -> 'AdditionalFormProvider':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_factory(self, factory: IAdditionalFormFactory):
        """
        Set the additional data form factory to use.

        Args:
            factory: Factory implementing IAdditionalFormFactory interface
        """
        self._factory = factory
        print(f"[AdditionalFormProvider] Using factory: {factory.__class__.__name__}")

    def create_form(self, parent: Optional[QWidget] = None) -> Optional[QWidget]:
        """
        Create an additional data form instance.

        Args:
            parent: Parent widget

        Returns:
            Form widget instance, or None if no factory is configured
        """
        if self._factory:
            return self._factory.create_form(parent)
        return None

    def has_factory(self) -> bool:
        """Check if a factory is registered"""
        return self._factory is not None

    def reset(self):
        """Reset to no factory (useful for testing)"""
        self._factory = None


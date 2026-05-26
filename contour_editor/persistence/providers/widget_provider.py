from typing import Optional, Protocol
from PyQt6.QtWidgets import QWidget, QDoubleSpinBox, QSpinBox, QLineEdit


class IWidgetFactory(Protocol):
    def create_double_spinbox(self, parent: Optional[QWidget] = None) -> QDoubleSpinBox:
        ...

    def create_spinbox(self, parent: Optional[QWidget] = None) -> QSpinBox:
        ...

    def create_lineedit(self, parent: Optional[QWidget] = None) -> QLineEdit:
        ...


class DefaultWidgetFactory:
    def create_double_spinbox(self, parent: Optional[QWidget] = None) -> QDoubleSpinBox:
        return QDoubleSpinBox(parent)

    def create_spinbox(self, parent: Optional[QWidget] = None) -> QSpinBox:
        return QSpinBox(parent)

    def create_lineedit(self, parent: Optional[QWidget] = None) -> QLineEdit:
        return QLineEdit(parent)


class WidgetProvider:
    _instance = None
    _factory: IWidgetFactory = None

    @classmethod
    def get(cls) -> 'WidgetProvider':
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._factory = DefaultWidgetFactory()
        return cls._instance

    def set_custom_factory(self, factory: IWidgetFactory):
        self._factory = factory
        print(f"[WidgetProvider] Using custom factory: {factory.__class__.__name__}")

    def create_double_spinbox(self, parent: Optional[QWidget] = None) -> QDoubleSpinBox:
        return self._factory.create_double_spinbox(parent)

    def create_spinbox(self, parent: Optional[QWidget] = None) -> QSpinBox:
        return self._factory.create_spinbox(parent)

    def create_lineedit(self, parent: Optional[QWidget] = None) -> QLineEdit:
        return self._factory.create_lineedit(parent)

    def reset(self):
        self._factory = DefaultWidgetFactory()


from typing import Optional, Protocol
from PyQt6.QtWidgets import QWidget, QMessageBox


class IDialogProvider(Protocol):
    def show_warning(self, parent: Optional[QWidget], title: str, message: str, info_text: str = "") -> bool:
        ...

    def show_error(self, parent: Optional[QWidget], title: str, message: str, info_text: str = "") -> None:
        ...

    def show_info(self, parent: Optional[QWidget], title: str, message: str, info_text: str = "") -> None:
        ...

    def show_success(self, parent: Optional[QWidget], title: str, message: str, info_text: str = "") -> None:
        ...


class DefaultDialogProvider:
    def show_warning(self, parent: Optional[QWidget], title: str, message: str, info_text: str = "") -> bool:
        full_message = f"{message}\n\n{info_text}" if info_text else message
        result = QMessageBox.warning(
            parent,
            title,
            full_message,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        return result == QMessageBox.StandardButton.Ok

    def show_error(self, parent: Optional[QWidget], title: str, message: str, info_text: str = "") -> None:
        full_message = f"{message}\n\n{info_text}" if info_text else message
        QMessageBox.critical(parent, title, full_message)

    def show_info(self, parent: Optional[QWidget], title: str, message: str, info_text: str = "") -> None:
        full_message = f"{message}\n\n{info_text}" if info_text else message
        QMessageBox.information(parent, title, full_message)

    def show_success(self, parent: Optional[QWidget], title: str, message: str, info_text: str = "") -> None:
        full_message = f"{message}\n\n{info_text}" if info_text else message
        QMessageBox.information(parent, title, full_message)


class DialogProvider:
    _instance = None
    _provider: IDialogProvider = None

    @classmethod
    def get(cls) -> 'DialogProvider':
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._provider = DefaultDialogProvider()
        return cls._instance

    def set_custom_provider(self, provider: IDialogProvider):
        self._provider = provider
        print(f"[DialogProvider] Using custom provider: {provider.__class__.__name__}")

    def show_warning(self, parent: Optional[QWidget], title: str, message: str, info_text: str = "") -> bool:
        return self._provider.show_warning(parent, title, message, info_text)

    def show_error(self, parent: Optional[QWidget], title: str, message: str, info_text: str = ""):
        self._provider.show_error(parent, title, message, info_text)

    def show_info(self, parent: Optional[QWidget], title: str, message: str, info_text: str = ""):
        self._provider.show_info(parent, title, message, info_text)

    def show_success(self, parent: Optional[QWidget], title: str, message: str, info_text: str = ""):
        self._provider.show_success(parent, title, message, info_text)

    def reset(self):
        self._provider = DefaultDialogProvider()


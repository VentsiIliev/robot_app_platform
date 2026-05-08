from typing import List, Optional, Tuple

from PyQt6.QtWidgets import QComboBox, QApplication, QWidget
from PyQt6.QtCore import pyqtSignal, QEvent

from pl_gui.shell.ui.styles import BORDER, PRIMARY, PRIMARY_DARK, TEXT_PRIMARY

_DEFAULT_LANGUAGES: List[Tuple[str, str]] = [("en", "English"), ("bg", "Bulgarian")]


class LanguageSelectorWidget(QComboBox):
    """
    Language selector that emits Qt LanguageChange events.

    When language changes:
    1. Emits custom languageChanged signal (emits the language code string)
    2. Posts QEvent.LanguageChange to all top-level widgets
    3. Widgets handle it in changeEvent() and call retranslateUi()
    """
    languageChanged = pyqtSignal(str)

    def __init__(self, languages: Optional[List[Tuple[str, str]]] = None, parent=None):
        super().__init__(parent)

        self.languages = languages if languages is not None else list(_DEFAULT_LANGUAGES)
        self._display_to_code = {display: code for code, display in self.languages}

        # Current language code (first entry is the default)
        self.current_language: str = self.languages[0][0]

        # Populate dropdown with display names
        self.addItems([display for _code, display in self.languages])
        self._apply_styles()

        # Set current language
        self.updateSelectedLang()

        self.currentIndexChanged.connect(self._on_language_change)

    def _on_language_change(self, index):
        """Handle language change and emit Qt LanguageChange events"""
        selected_text = self.currentText()
        code = self._display_to_code[selected_text]

        # Update current language
        self.current_language = code

        # Emit language code string
        self.languageChanged.emit(code)

        # Post LanguageChange event to all top-level widgets (Qt standard way)
        self._post_language_change_events()

    def _post_language_change_events(self):
        """Post LanguageChange event to top-level widgets and their descendants."""
        app = QApplication.instance()
        if app and isinstance(app, QApplication):
            posted = 0
            for widget in app.topLevelWidgets():
                if not isinstance(widget, QWidget):
                    continue
                app.postEvent(widget, QEvent(QEvent.Type.LanguageChange))
                posted += 1
                for child in widget.findChildren(QWidget):
                    app.postEvent(child, QEvent(QEvent.Type.LanguageChange))
                    posted += 1
            print(f"[LanguageSelector] Posted LanguageChange events to {posted} widgets")

    def updateSelectedLang(self):
        """Update the selected language in the dropdown"""
        # Find display name for current language code
        for code, display in self.languages:
            if code == self.current_language:
                self.setCurrentIndex(self.findText(display))
                return

    def _apply_styles(self) -> None:
        """Keep the shell language selector readable across hover and popup states."""
        self.setStyleSheet(
            f"""
            QComboBox {{
                background-color: white;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                min-height: 28px;
            }}
            QComboBox:hover,
            QComboBox:focus,
            QComboBox:on {{
                color: {TEXT_PRIMARY};
                border: 1px solid {PRIMARY};
                background-color: #F7F1FB;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background: white;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                outline: none;
                selection-background-color: #EDE7F6;
                selection-color: {TEXT_PRIMARY};
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 28px;
                padding: 6px 10px;
                color: {TEXT_PRIMARY};
                background: white;
            }}
            QComboBox QAbstractItemView::item:hover,
            QComboBox QAbstractItemView::item:selected {{
                color: {TEXT_PRIMARY};
                background: #EDE7F6;
            }}
            QComboBox QAbstractItemView::item:selected:active {{
                color: white;
                background: {PRIMARY_DARK};
            }}
            """
        )

from typing import List, Optional, Tuple

from PyQt6.QtWidgets import QComboBox, QApplication
from PyQt6.QtCore import pyqtSignal, QEvent

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
        """Post LanguageChange event to all top-level widgets in the application"""
        app = QApplication.instance()
        if app and isinstance(app, QApplication):
            for widget in app.topLevelWidgets():
                event = QEvent(QEvent.Type.LanguageChange)
                app.postEvent(widget, event)
            print(f"[LanguageSelector] Posted LanguageChange events to {len(app.topLevelWidgets())} top-level widgets")

    def updateSelectedLang(self):
        """Update the selected language in the dropdown"""
        # Find display name for current language code
        for code, display in self.languages:
            if code == self.current_language:
                self.setCurrentIndex(self.findText(display))
                return



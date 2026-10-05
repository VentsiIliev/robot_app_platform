from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QMessageBox
from src.applications.base.i_application_view import IApplicationView
from pl_gui.settings.settings_view.styles import BG_COLOR, APP_PAGE_TITLE_STYLE, ACTION_BTN_STYLE, GHOST_BTN_STYLE


class SoftwareUpdateView(IApplicationView):
    SHOW_JOG_WIDGET = False
    check_requested = pyqtSignal()
    download_requested = pyqtSignal()
    install_requested = pyqtSignal()

    def __init__(self, parent=None):
        self._values = {"installed": "", "staged": "", "configuration": ""}
        self._status_source = "Ready"
        self._status_arguments = {}
        self._error = ""
        super().__init__("SoftwareUpdate", parent)
        self.retranslateUi()

    def setup_ui(self):
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        layout = QVBoxLayout(self)
        self._title = QLabel()
        self._title.setStyleSheet(APP_PAGE_TITLE_STYLE)
        self._details = QLabel()
        self._details.setTextFormat(Qt.TextFormat.PlainText)
        self._details.setWordWrap(True)
        self._description = QLabel()
        self._description.setWordWrap(True)
        self._status = QLabel()
        self._status.setTextFormat(Qt.TextFormat.PlainText)
        self._status.setWordWrap(True)
        self._check = QPushButton()
        self._download = QPushButton()
        self._install = QPushButton()
        for button in (self._check, self._download, self._install):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(ACTION_BTN_STYLE if button is self._install else GHOST_BTN_STYLE)
        self._check.clicked.connect(self._on_check)
        self._download.clicked.connect(self._on_download)
        self._install.clicked.connect(self._on_install)
        for widget in (self._title, self._details, self._description, self._check, self._download, self._install, self._status):
            layout.addWidget(widget)
        layout.addStretch()
        self._install.setEnabled(False)

    def _on_check(self): self.check_requested.emit()
    def _on_download(self): self.download_requested.emit()
    def _on_install(self): self.install_requested.emit()

    def set_details(self, details):
        self._values = details
        self.retranslateUi()

    def set_actions(self, busy: bool, enabled: bool, staged: bool):
        self._check.setEnabled(not busy)
        self._download.setEnabled(not busy and enabled)
        self._install.setEnabled(not busy and staged)

    def set_status(self, source, **arguments):
        self._status_source = source
        self._status_arguments = arguments
        self._error = ""
        self.retranslateUi()

    def set_error(self, error):
        self._error = error
        self.retranslateUi()

    def show_check_result(self, error=False):
        """Make an explicitly requested check result visible above the screen."""
        title = self.tr("Software Update") or "Software Update"
        if error:
            QMessageBox.critical(self, title, self._status.text())
        else:
            QMessageBox.information(self, title, self._status.text())

    def retranslateUi(self):
        self._title.setText(self.tr("Software Update") or "Software Update")
        self._check.setText(self.tr("Check for updates") or "Check for updates")
        self._download.setText(self.tr("Download update") or "Download update")
        self._install.setText(self.tr("Install after application closes") or "Install after application closes")
        source = "Installed: {installed}\nDownloaded: {staged}\nConfiguration: {configuration}"
        self._details.setText((self.tr(source) or source).format(**self._values))
        source = "Updates change the platform only. Stop production and close the application normally after scheduling installation. The launcher installs the update and reopens the platform."
        self._description.setText(self.tr(source) or source)
        self._status.setText(self._error or (self.tr(self._status_source) or self._status_source).format(**self._status_arguments))

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange and hasattr(self, "_title"):
            self.retranslateUi()
        super().changeEvent(event)

    def clean_up(self):
        pass

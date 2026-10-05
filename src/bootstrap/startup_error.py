"""Report fatal startup failures to desktop users as well as the terminal."""
import os
from pathlib import Path
import sys
import traceback


def report_startup_error(error: Exception, log_directory: Path) -> None:
    """Persist the traceback and show a modal dialog; never start robot services."""
    details = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    print(details, file=sys.stderr)
    try:
        log_directory.mkdir(parents=True, exist_ok=True)
        log_path = log_directory / "last-startup-error.log"
        log_path.write_text(details, encoding="utf-8")
        details += f"\nLog: {log_path}\n"
    except OSError as log_error:
        details += f"\nCould not save error log: {log_error}\n"
    try:
        _show_error_dialog(str(error), details)
    except Exception as dialog_error:
        print(f"Could not display startup error: {dialog_error}", file=sys.stderr)


def _show_error_dialog(error_text: str, details: str) -> None:
    from PyQt6.QtCore import QCoreApplication, QLibraryInfo, Qt
    from PyQt6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance()
    if app is None:
        # OpenCV can redirect Qt to its incompatible Qt5 plugin directory.
        # Use this application's Qt6 plugins when reporting pre-GUI failures.
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
        os.environ.pop("QT_PLUGIN_PATH", None)
        app = QApplication([])
    def translate(text):
        return QCoreApplication.translate("StartupError", text) or text

    dialog = QMessageBox()
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle(translate("Platform could not start"))
    dialog.setTextFormat(Qt.TextFormat.PlainText)
    dialog.setText(translate("The platform stopped because an error occurred."))
    dialog.setInformativeText(error_text)
    dialog.setDetailedText(details)
    dialog.setStandardButtons(QMessageBox.StandardButton.Close)
    dialog.exec()

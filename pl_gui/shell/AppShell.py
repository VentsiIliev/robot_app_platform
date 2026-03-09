from typing import Callable, List
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QStackedWidget, QFrame, QWidget)
from PyQt6.QtWidgets import (QVBoxLayout, QApplication)

from pl_gui.shell.app_descriptor import AppDescriptor
from pl_gui.shell.ui.Header import Header
from pl_gui.shell.FolderLauncher import FolderLauncher, FolderConfig
from pl_gui.shell.shell_config import ShellConfig


class AppShell(QWidget):
    """Pure Qt shell - knows nothing about plugins_example, applications, or business logic"""
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()

    def __init__(
        self,
        app_descriptors: List[AppDescriptor],
        widget_factory: Callable[[str], QWidget],
        ui_factory=None,
        languages: list = None
    ):
        """
        Args:
            app_descriptors: List of apps to display in folders
            widget_factory: Callable that creates widgets given an app name
            ui_factory: Optional UIFactory for swappable UI components (defaults to MaterialUIFactory)
            languages: Optional list of (code, display_name) tuples for language selector.
                       Defaults to [("en", "English"), ("bg", "Bulgarian")].
        """
        super().__init__()

        # Store injected dependencies
        self._app_descriptors = app_descriptors
        self._widget_factory = widget_factory

        from pl_gui.shell.ui.material import MaterialUIFactory
        self._ui_factory = ui_factory or MaterialUIFactory()
        self._languages = languages

        # Internal state
        self.current_running_app = None  # Track currently running app
        self.current_app_folder = None  # Track which folder has the running app
        self.stacked_widget = None  # The main stacked widget
        self.folders_page = None  # The folders page widget
        self.pending_camera_operations = False  # Track if camera operations are in progress
        self.running_widgets = {}  # app_name -> widget


        self.setup_ui()

    def on_folder_opened(self, opened_folder):
        """Handle when a folder is opened - gray out other folders"""
        # This is now handled by the FoldersPage, but we keep it for compatibility
        pass

    def on_folder_closed(self):
        """Handle when a folder is closed - restore all folders"""
        print("MainWindow: Folder closed - restoring all folders")
        # Reset the current app state
        self.current_running_app = None
        self.current_app_folder = None

    def on_app_selected(self, app_name):
        """Handle when an app is selected from any folder"""
        print(f"Currently running app: {self.current_running_app}")
        print(f"MainWindow: App selected - {app_name}")

        # Find which folder emitted this signal by looking at the folders page
        sender_folder = None
        for folder in self.folders_page.get_folders():
            if folder == self.sender():
                sender_folder = folder
                break

        # Store the running app info
        self.current_running_app = app_name
        self.current_app_folder = sender_folder
        # Show the appropriate app
        self.show_app(app_name)

    def on_back_button_pressed(self):
        """Handle when the back button is pressed in the sidebar"""
        print("MainWindow: Back button signal received - closing app and returning to main")
        self.close_current_app()



    def create_app(self, app_name: str) -> QWidget:
        """Create app widget using injected factory - ONE LINE!"""
        print(f"MainWindow: Creating app widget for '{app_name}'")
        return self._widget_factory(app_name)



    def show_app(self, app_name):
        # Check if widget already exists
        if app_name in self.running_widgets:
            app_widget = self.running_widgets[app_name]
        else:
            app_widget = self.create_app(app_name)
            self.running_widgets[app_name] = app_widget

        print("MAIN_WINDOW LEN RUNNING WIDGETS:", len(self.running_widgets))

        # Connect signals if not already connected
        if not getattr(app_widget, "_signals_connected", False):
            app_widget.app_closed.connect(self.close_current_app)
            app_widget._signals_connected = True

        # Remove old widget visually but keep it alive
        if self.stacked_widget.count() > 1:
            old_app = self.stacked_widget.widget(1)
            self.stacked_widget.removeWidget(old_app)
            # Don't deleteLater() here!

        self.stacked_widget.addWidget(app_widget)
        self.stacked_widget.setCurrentIndex(1)
        return app_widget


    def close_all_apps(self):
        """
        Close all cached app widgets and restore the folder interface.
        Useful when logging out or shutting down.
        """

        # Give each widget a chance to veto the close
        for app_widget in self.running_widgets.values():
            if app_widget and hasattr(app_widget, "can_close") and not app_widget.can_close():
                return
        print("MainWindow: Closing all running apps...")

        # Only manage OUR cache - no plugin_widget_factory access!
        for app_name, app_widget in list(self.running_widgets.items()):
            if not app_widget:
                continue

            print(f"Closing app widget: {app_name}")

            # Call any cleanup method if it exists
            if hasattr(app_widget, "clean_up"):
                try:
                    app_widget.clean_up()
                except Exception as e:
                    print(f"Error cleaning up widget {app_name}: {e}")

            # Remove from stacked widget if present
            if self.stacked_widget.indexOf(app_widget) != -1:
                self.stacked_widget.removeWidget(app_widget)

            # Delete the widget safely
            try:
                app_widget.deleteLater()
            except Exception as e:
                print(f"Error deleting widget {app_name}: {e}")

        # Clear our cache
        self.running_widgets.clear()

        # Reset current app info

        self.current_running_app = None
        self.current_app_folder = None

        # Go back to folders page
        self.stacked_widget.setCurrentIndex(0)
        print("MainWindow: All apps closed, back to folder view.")

    def close_current_app(self):
        self.close_all_apps()

    def setup_ui(self):
        self.setWindowTitle("PL Project")
        # Set a reasonable window size instead of maximized
        self.resize(1280, 1024)  # Reasonable default size
        # Center the window on screen
        self.center_on_screen()
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(248, 250, 252, 1),
                    stop:1 rgba(241, 245, 249, 1));
            }
        """)

        # Create main layout for the window
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Machine indicator toolbar at the very top ---
        screen_width = QApplication.primaryScreen().size().width()
        screen_height = QApplication.primaryScreen().size().height()
        self.header = Header(screen_width,
                             screen_height,
                             toggle_menu_callback=None,
                             dashboard_button_callback=None,
                             languages=self._languages)
        self.header.menu_button.setVisible(False)
        self.header.dashboardButton.setVisible(False)
        self.header.power_toggle_button.setVisible(False)
        # self.header.user_account_clicked.connect(self.show_session_info_widget)

        machine_toolbar_frame = QFrame()
        machine_toolbar_frame.setFrameShape(QFrame.Shape.StyledPanel)
        machine_toolbar_frame.setStyleSheet("background-color: #FFFBFE; border: 1px solid #E7E0EC;")
        machine_toolbar_layout = QVBoxLayout(machine_toolbar_frame)
        machine_toolbar_layout.setContentsMargins(5, 5, 5, 5)
        machine_toolbar_layout.addWidget(self.header)

        main_layout.addWidget(machine_toolbar_frame)

        # Create the stacked widget
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # Create and add the folders page (index 0)
        self.create_folders_page()

        # Setup keyboard shortcuts
        # self.setup_keyboard_shortcuts()

    def create_folders_page(self):
        """Create and configure the folders page from AppDescriptors"""

        def translate_fn(translation_key):
            return self.tr(translation_key)

        # Build apps from descriptors - NO plugin manager access!
        filtered_apps = {}

        for desc in self._app_descriptors:
            if desc.folder_id not in filtered_apps:
                filtered_apps[desc.folder_id] = []
            filtered_apps[desc.folder_id].append([desc.name, desc.icon_str])
            print(f"[AppShell] Added {desc.name} to folder {desc.folder_id}")

        # Build folder configs from centralized configuration
        folder_config_list = []

        for folder_def in ShellConfig.get_folders_with_apps(filtered_apps):
            folder_config_list.append(FolderConfig(
                ID=folder_def.id,
                name=folder_def.name,
                apps=filtered_apps[folder_def.id],
                translate_fn=folder_def.get_translate_fn()
            ))

        if self.folders_page:
            self.stacked_widget.removeWidget(self.folders_page)
            self.folders_page.deleteLater()

        self.folders_page = FolderLauncher(
            folder_config_list=folder_config_list, main_window=self, ui_factory=self._ui_factory
        )

        # Connect signals from the folders page
        self.folders_page.folder_opened.connect(self.on_folder_opened)
        self.folders_page.folder_closed.connect(self.on_folder_closed)
        self.folders_page.app_selected.connect(self.on_app_selected)
        self.folders_page.close_current_app_requested.connect(self.close_current_app)

        # Add the folders page to the stacked widget (index 0)
        self.stacked_widget.addWidget(self.folders_page)

    def retranslate(self):
        """Handle language change events - called automatically"""
        # Update existing folder titles instead of recreating everything
        if hasattr(self, 'folders_page') and self.folders_page:
            # Get all folder widgets and update their titles
            for folder_widget in self.folders_page.get_folder_widgets():
                if hasattr(folder_widget, 'update_title_label'):
                    folder_widget.update_title_label()

    def center_on_screen(self):
        """Center the window on the screen"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            window_geometry = self.frameGeometry()
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)
            self.move(window_geometry.topLeft())

    def resizeEvent(self, event):
        """Handle window resize to maintain proper layout"""
        super().resizeEvent(event)
        # The responsive folders will handle their own sizing

    def sizeHint(self):
        """Provide a reasonable size hint for the window"""
        # Calculate size based on folder grid (3x2) plus margins
        folder_size = 350  # Approximate folder width
        spacing = 30
        margins = 80  # Total margins (40 on each side)

        width = (folder_size * 3) + (spacing * 2) + margins
        height = (folder_size * 2) + spacing + margins

        return self.size() if hasattr(self, '_initialized') else self.size()

    def keyPressEvent(self, event):
        """Handle key press events"""
        # ESC key to close current app (for demo purposes)
        if event.key() == Qt.Key.Key_Escape and self.current_running_app:
            self.close_current_app()
        super().keyPressEvent(event)

    def changeEvent(self, event):
        """Handle Qt events - particularly LanguageChange"""
        if event.type() == event.Type.LanguageChange:
            print("[MainWindow] Received LanguageChange event")
            self.retranslate()
        super().changeEvent(event)

    def lock(self):
        """Lock the GUI to prevent interaction"""
        self.setEnabled(False)
        print("GUI locked")

    def unlock(self):
        """Unlock the GUI to allow interaction"""
        self.setEnabled(True)
        print("GUI unlocked")

    def cleanup(self):
        """Cleanup resources when main window is closed"""
        try:
            print("MainWindow: Cleaning up...")
            # Only clean our own resources
            self.close_all_apps()
            print("MainWindow: Cleanup complete")
        except Exception as e:
            print(f"Error during MainWindow cleanup: {e}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.cleanup()
        super().closeEvent(event)

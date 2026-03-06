from dataclasses import dataclass

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QSizePolicy,
                             QApplication)
from typing import Callable

# CHANGE: Import only FolderController - FolderWidget comes from UIFactory
from pl_gui.shell.folder_controller import FolderController

@dataclass
class FolderConfig:
    ID: int
    name: str
    apps: list
    translate_fn: Callable = None  # Optional translation callback


class FolderLauncher(QWidget):
    """Manages the main folders page layout using FolderController vision_service"""

    # Signals to communicate with the main window
    folder_opened = pyqtSignal(object)  # FolderController object
    folder_closed = pyqtSignal()
    app_selected = pyqtSignal(str)  # App name
    close_current_app_requested = pyqtSignal()

    def __init__(self, parent=None, folder_config_list=None, main_window=None, ui_factory=None):
        super().__init__(parent)
        self.folder_config_list = folder_config_list
        self.folder_controllers = []  # Track all folder controllers
        self.folder_widgets = []  # Track all folder widgets
        self.main_window = main_window  # Store main window reference
        self.ui_factory = ui_factory
        self.setup_ui()

    def setup_ui(self):
        """Set up the main UI for the folders page"""
        # Main container widget with size constraints
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        # Use a main layout to center the container
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(40, 40, 40, 40)
        page_layout.addWidget(container, 0, Qt.AlignmentFlag.AlignCenter)

        # Grid layout for folders with controlled spacing
        layout = QGridLayout(container)
        layout.setSpacing(30)  # Reasonable spacing between folders
        layout.setContentsMargins(0, 0, 0, 0)

        # Create and configure all folders
        self.__create_folders()

        # Add folders to grid (3 columns, 2 rows) with center alignment
        self.__add_folders_to_layout(layout)

        # Set the container to use its content size
        container.adjustSize()

    def __create_folders(self):
        """Create all folders using the new FolderController vision_service"""
        for config in self.folder_config_list:
            ID = config.ID
            folder_name = config.name
            apps = config.apps
            translate_fn = config.translate_fn

            # Create folder widget and controller
            folder_widget, folder_controller = self.__create_folder(ID,folder_name, apps,translate_fn)

            # Store both widget and controller
            self.folder_widgets.append(folder_widget)
            self.folder_controllers.append(folder_controller)

        # Connect signals after all folders are created
        self.__connect_folder_signals()

    def __create_folder(self, ID,folder_name, apps,translate_fn):

        """Create a folder widget and its controller"""
        # Create folder widget via factory
        folder_widget = self.ui_factory.create_folder_widget(ID, folder_name)
        folder_widget.translate_fn = translate_fn

        # Add apps to folder widget
        for widget_type, icon_path in apps:
            folder_widget.add_app(widget_type, icon_path)

        # Create controller with factory injection
        folder_controller = FolderController(folder_widget, self.main_window, ui_factory=self.ui_factory)

        return folder_widget, folder_controller

    def __add_folders_to_layout(self, layout):
        """Add folder widgets to the grid layout dynamically"""
        columns = 3
        for idx, folder_widget in enumerate(self.folder_widgets):
            row = idx // columns
            col = idx % columns
            layout.addWidget(folder_widget, row, col, Qt.AlignmentFlag.AlignCenter)

    def __connect_folder_signals(self):
        """Connect signals for all folder controllers"""
        for folder_controller in self.folder_controllers:
            # Connect controller signals to local handlers
            folder_controller.folder_opened.connect(self.on_folder_opened)
            folder_controller.folder_closed.connect(self.on_folder_closed)
            folder_controller.app_selected.connect(self.on_app_selected)
            folder_controller.close_current_app_signal.connect(self.on_close_current_app_requested)

    def on_folder_opened(self, opened_folder_controller=None):
        """Handle when a folder is opened - gray out other folders"""
        # print(f"FoldersPage: Folder opened by controller")

        # Find which controller opened
        opened_controller = self.sender() if opened_folder_controller is None else opened_folder_controller

        # # Gray out other folders
        # for folder_controller in self.folder_controllers:
        #     if folder_controller != opened_controller:
        #         folder_controller.set_disabled(True)

        # Emit signal to main window - pass the controller instead of old folder object
        self.folder_opened.emit(opened_controller)

    def enable_folder_by_id(self, ID):
        """Enable a folder by its name"""
        for folder_controller in self.folder_controllers:
            if folder_controller.folder_widget.ID == ID:
                folder_controller.set_disabled(False)
                # print(f"FoldersPage: Enabled folder '{ID}'")
                return
        # print(f"FoldersPage: Folder with ID ='{ID}' not found to enable")

    def disable_folder_by_id(self, ID):
        """Disable a folder by its name"""
        for folder_controller in self.folder_controllers:
            if folder_controller.folder_widget.ID == ID:
                folder_controller.set_disabled(True)
                # print(f"FoldersPage: Disabled folder '{ID}'")
                return
        # print(f"FoldersPage: Folder with ID ='{ID}' not found to disable")

    def on_folder_closed(self):
        """Handle when a folder is closed - restore all folders"""
        # print("FoldersPage: Folder closed - restoring all folders")

        # # Restore all folders
        # for folder_controller in self.folder_controllers:
        #     folder_controller.set_disabled(False)

        # Emit signal to main window
        self.folder_closed.emit()

    def on_app_selected(self, app_name):
        """Handle when an app is selected from any folder"""
        # print(f"FoldersPage: App selected - {app_name}")
        # Emit signal to main window
        self.app_selected.emit(app_name)

    def on_close_current_app_requested(self):
        """Handle when close current app is requested"""
        # print("FoldersPage: Close current app requested")
        # Emit signal to main window
        self.close_current_app_requested.emit()

    def get_folders(self):
        """Get the list of all folder controllers (updated for compatibility)"""
        return self.folder_controllers

    def get_folder_controllers(self):
        """Get the list of all folder controllers"""
        return self.folder_controllers

    def get_folder_widgets(self):
        """Get the list of all folder widgets"""
        return self.folder_widgets



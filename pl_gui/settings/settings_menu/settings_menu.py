from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import qtawesome as qta
from src.settings.settings_view.styles import PRIMARY, PRIMARY_LIGHT
from .menu_icon import MenuIcon



class SettingsMenu(QWidget):
    """
    Settings menu plugin that displays clickable icons for different settings categories.

    Signals:
        settings_selected(str): Emitted when a settings category is clicked (setting_id)

    Args:
        categories: List of category dicts with 'id', 'title', 'icon', 'description' keys.
                   If None, uses default categories.
        compact: Whether to use compact mode (for sidebar)
        parent: Parent widget
    """

    settings_selected = pyqtSignal(str)

    def __init__(self, categories, compact: bool = False, parent=None):
        super().__init__(parent)
        self.compact_mode = compact
        self.menu_items = {}
        self.categories = categories
        self._init_ui()


    def _init_ui(self):
        main_layout = QVBoxLayout()

        if not self.compact_mode:
            main_layout.setContentsMargins(20, 20, 20, 20)

            # Header
            header = QLabel("Settings")
            header_font = QFont()
            header_font.setPointSize(24)
            header_font.setBold(True)
            header.setFont(header_font)
            header.setStyleSheet("color: #333; margin-bottom: 10px;")
            main_layout.addWidget(header)

            # Subtitle
            subtitle = QLabel("Choose a settings category to configure")
            subtitle.setStyleSheet("color: #666; font-size: 14px; margin-bottom: 20px;")
            main_layout.addWidget(subtitle)
        else:
            main_layout.setContentsMargins(5, 10, 5, 10)

        # Scroll area for settings items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        grid_layout = QVBoxLayout()
        grid_layout.setSpacing(10 if self.compact_mode else 15)

        # Create rows of items
        items_per_row = 1 if self.compact_mode else 3
        row_layout = None
        for i, category in enumerate(self.categories):
            if i % items_per_row == 0:
                row_layout = QHBoxLayout()
                row_layout.setSpacing(10 if self.compact_mode else 15)
                grid_layout.addLayout(row_layout)

            if self.compact_mode:
                # Use MenuIcon for sidebar (Material Design)
                item = MenuIcon(
                    icon_label=category.id,
                    icon_path=category.icon,
                    icon_text="",
                    parent=self
                )
                item.set_material_size("compact")  # 80x80
                item.button_clicked.connect(lambda label, cat_id=category.id: self._on_item_clicked(cat_id))
                self.menu_items[category.id] = item
                row_layout.addWidget(item)


        # Add stretch to push items to top
        if row_layout and not self.compact_mode:
            row_layout.addStretch()
        grid_layout.addStretch()

        scroll_content.setLayout(grid_layout)
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        self.setLayout(main_layout)

    def _on_item_clicked(self, setting_id: str):
        """Handle settings item click"""
        print(f"[SettingsMenuPlugin] Settings selected: {setting_id}")
        self.set_active_item(setting_id)
        self.settings_selected.emit(setting_id)

    def set_active_item(self, setting_id: str):
        """Mark a specific item as active/selected"""
        for item_id, item in self.menu_items.items():
            if isinstance(item, MenuIcon):
                # MenuIcon uses style variants for active state
                if item_id == setting_id:
                    item.set_material_style("primary")  # Active style
                else:
                    item.set_material_style("secondary")  # Inactive style
            else:
                # SettingsMenuItem uses set_selected
                item.set_selected(item_id == setting_id)


class SettingsNavigationWidget(QWidget):
    """
    Combined navigation widget with sidebar menu and content area.
    Icons remain visible for quick switching between settings.

    Args:
        categories: List of category dicts with 'id', 'title', 'icon', 'description' keys.
                   If None, uses default categories from SettingsMenu.
        factory_map: Dict mapping category IDs to factory functions that create widgets.
                    e.g., {"robot": lambda: RobotConfigUI(), "camera": create_camera_settings}
                    If provided, views are automatically created for all categories.
        parent: Parent widget

    Signals:
        tab_changing(str, str): Emitted before tab changes (old_tab_id, new_tab_id)
        tab_changed(str, str): Emitted after tab changes (old_tab_id, new_tab_id)
    """

    tab_changing = pyqtSignal(str, str)  # old_tab_id, new_tab_id
    tab_changed = pyqtSignal(str, str)   # old_tab_id, new_tab_id

    def __init__(self, categories, factory_map, parent=None):
        super().__init__(parent)
        self.categories = categories
        self.factory_map = factory_map or {}
        self.settings_views = {}
        self.current_tab_id = None  # Track current tab
        self._init_ui()
        self._create_views_from_factory()

    def _init_ui(self):
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left sidebar with compact menu
        self.sidebar = SettingsMenu(categories=self.categories, compact=True)
        self.sidebar.setFixedWidth(100)
        self.sidebar.setStyleSheet("background-color: #f8f8f8; border-right: 1px solid #e0e0e0;")
        self.sidebar.settings_selected.connect(self._show_settings)
        main_layout.addWidget(self.sidebar)

        # Right content area
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background-color: white;")
        main_layout.addWidget(self.content_stack, 1)

        # Add welcome page as page 0
        welcome = self._create_welcome_page()
        self.content_stack.addWidget(welcome)

        self.setLayout(main_layout)

    def _create_welcome_page(self):
        """Create welcome/placeholder page"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Welcome message
        title = QLabel("Welcome to Settings")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)
        title.setStyleSheet("color: #333; margin: 50px;")
        layout.addWidget(title)

        desc = QLabel("Click on any icon in the sidebar to configure settings.\n\n"
                     "Icons remain visible for quick switching between categories.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 14px;")
        layout.addWidget(desc)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _create_views_from_factory(self):
        """Automatically create views from factory_map"""
        if not self.factory_map:
            return

        # Get categories to create views for
        categories_to_use = self.categories or SettingsMenu._get_default_categories()

        for category in categories_to_use:
            category_id = category.id
            if category_id in self.factory_map:
                factory = self.factory_map[category_id]
                try:
                    # Call factory to create widget
                    widget = factory() if callable(factory) else factory
                    self.add_settings_view(category_id, widget)
                    print(f"[Navigation] Auto-created view for '{category_id}'")
                except Exception as e:
                    print(f"[Navigation] Error creating view for '{category_id}': {e}")

    def add_settings_view(self, setting_id: str, widget: QWidget):
        """Add a settings view for a specific category"""
        index = self.content_stack.addWidget(widget)
        self.settings_views[setting_id] = index

    def _show_settings(self, setting_id: str):
        """Show the selected settings view"""
        if setting_id in self.settings_views:
            old_tab_id = self.current_tab_id

            # Emit signal before changing tab
            if old_tab_id:
                self.tab_changing.emit(old_tab_id, setting_id)

            # Notify previous widget if it has a deactivate method
            if old_tab_id and old_tab_id in self.settings_views:
                old_index = self.settings_views[old_tab_id]
                old_widget = self.content_stack.widget(old_index)
                if hasattr(old_widget, 'on_tab_deactivate'):
                    old_widget.on_tab_deactivate()

            # Switch to new tab
            index = self.settings_views[setting_id]
            self.content_stack.setCurrentIndex(index)
            self.current_tab_id = setting_id

            # Notify new widget if it has an activate method
            new_widget = self.content_stack.widget(index)
            if hasattr(new_widget, 'on_tab_activate'):
                new_widget.on_tab_activate()

            # Emit signal after changing tab
            if old_tab_id:
                self.tab_changed.emit(old_tab_id, setting_id)

            print(f"[Navigation] Tab changed: {old_tab_id or 'None'} → {setting_id}")
        else:
            print(f"[Navigation] No view registered for {setting_id}")
            # Show welcome page
            self.content_stack.setCurrentIndex(0)
            self.current_tab_id = None

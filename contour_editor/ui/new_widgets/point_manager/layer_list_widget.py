from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import QListWidget, QListWidgetItem

from contour_editor.ui.new_widgets.LayerButtonsWidget import LayerButtonsWidget
from .models import ListItemData
from .list_item_widgets import ExpandableLayerWidget
from ..styles import PRIMARY, PRIMARY_DARK, BORDER


class LayerListWidget(QListWidget):
    layer_expanded = pyqtSignal(str, bool)
    layer_clicked = pyqtSignal(str)

    def __init__(self, segment_actions, expanded_layers, parent=None):
        super().__init__(parent)
        self.segment_actions = segment_actions
        self.expanded_layers = expanded_layers
        self.layer_items = {}

        # Apply modern styling matching other new_widgets
        self.setStyleSheet(f"""
            QListWidget {{
                outline: none;
                border: 1px solid {BORDER};
                background-color: white;
                border-radius: 8px;
                font-family: Arial;
                font-size: 11pt;
            }}
            QListWidget::item {{
                border: none;
                padding: 12px 4px;
                margin: 6px 2px;
                border-radius: 6px;
            }}
            QListWidget::item:selected {{
                background-color: rgba(122,90,248,0.15);
                border: 1px solid {PRIMARY};
                color: {PRIMARY_DARK};
            }}
            QListWidget::item:hover {{
                background-color: rgba(122,90,248,0.05);
            }}
        """)

        self.setAlternatingRowColors(False)  # Disable default alternating colors
        self.itemClicked.connect(self._on_item_clicked)

    def initialize_layers(self, contour_editor):
        """Initialize layer items"""
        self.clear()
        self.layer_items = {}

        layer_names = contour_editor.manager.get_available_layer_names() if contour_editor else []
        for name in layer_names:
            self._create_layer_item(name, contour_editor)

    def _create_layer_item(self, name, contour_editor):
        """Create a layer item with proper configuration"""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 72))

        item_data = ListItemData('layer', layer_name=name)
        item.setData(Qt.ItemDataRole.UserRole, item_data)

        is_locked = contour_editor.manager.isLayerLocked(name) if contour_editor else False
        layer_buttons = LayerButtonsWidget(
            layer_name=name,
            layer_item=item,
            on_visibility_toggle=lambda visible, n=name: self.segment_actions.set_layer_visibility(n, visible),
            on_add_segment=self.segment_actions.make_add_segment(name, self.expanded_layers),
            on_lock_toggle=self.segment_actions.make_layer_lock_toggle(name),
            is_locked=is_locked
        )

        expandable_widget = ExpandableLayerWidget(
            name,
            layer_buttons,
            self._on_expand_toggle
        )

        is_expanded = name in self.expanded_layers
        expandable_widget.set_expanded(is_expanded)

        self.addItem(item)
        self.setItemWidget(item, expandable_widget)

        self.layer_items[name] = item

    def _on_expand_toggle(self, layer_name, is_expanded):
        """Handle layer expand/collapse"""
        self.layer_expanded.emit(layer_name, is_expanded)

    def _on_item_clicked(self, item):
        """Handle layer selection"""
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if item_data and item_data.item_type == 'layer':
            self.layer_clicked.emit(item_data.layer_name)

    def get_layer_item(self, layer_name):
        """Get the QListWidgetItem for a layer"""
        return self.layer_items.get(layer_name)

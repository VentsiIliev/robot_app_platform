from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import QListWidget, QListWidgetItem

from ...new_widgets.SegmentButtonsAndComboWidget import SegmentButtonsAndComboWidget
from .models import ListItemData
from .list_item_widgets import ExpandableSegmentWidget, IndentedWidget
from ..styles import PRIMARY, PRIMARY_DARK, BORDER


class SegmentListWidget(QListWidget):
    segment_expanded = pyqtSignal(int, bool)
    segment_clicked = pyqtSignal(int)

    def __init__(self, segment_actions, settings_handler, expanded_segments, parent=None):
        super().__init__(parent)
        self.segment_actions = segment_actions
        self.settings_handler = settings_handler
        self.expanded_segments = expanded_segments
        self.segment_items = {}

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
                padding: 8px 4px;
                margin: 4px 2px;
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

        self.setAlternatingRowColors(False)  # Modern design uses hover/selection instead
        self.itemClicked.connect(self._on_item_clicked)

    def add_segment(self, seg_index, segment, layer_name, contour_editor):
        """Add a segment item to the list"""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 100))

        item_data = ListItemData('segment', layer_name=layer_name, seg_index=seg_index)
        item.setData(Qt.ItemDataRole.UserRole, item_data)

        seg_container = self._create_segment_container(
            item, seg_index, segment, layer_name, contour_editor
        )

        expandable_widget = ExpandableSegmentWidget(
            seg_index,
            seg_container,
            self._on_expand_toggle
        )

        is_expanded = seg_index in self.expanded_segments
        expandable_widget.set_expanded(is_expanded)

        indented_widget = IndentedWidget(expandable_widget, indent_level=1)

        self.addItem(item)
        self.setItemWidget(item, indented_widget)

        self.segment_items[seg_index] = item

    def _create_segment_container(self, seg_item, seg_index, segment, layer_name, contour_editor):
        """Create the segment button container with all callbacks"""
        def on_visibility(btn):
            if self.segment_actions.segment_service:
                self.segment_actions.segment_service.toggle_visibility(seg_index)
            else:
                from contour_editor.services.commands import ToggleSegmentVisibilityCommand
                cmd = ToggleSegmentVisibilityCommand(
                    contour_editor.manager,
                    seg_index
                )
                self.segment_actions.command_history.execute(cmd)

        def on_activate():
            self.segment_actions.set_active_segment_ui(seg_index)

        def on_delete():
            self.segment_actions.delete_segment(seg_index)

        def on_settings():
            self.settings_handler.on_settings_button_clicked(seg_index)

        def on_layer_change(new_layer_name):
            self.segment_actions.assign_segment_layer(seg_index, new_layer_name)

        def on_long_press(seg_idx):
            print(f"Long press detected on segment {seg_idx}!")

        return SegmentButtonsAndComboWidget(
            seg_index=seg_index,
            segment=segment,
            layer_name=layer_name,
            on_visibility=on_visibility,
            on_activate=on_activate,
            on_delete=on_delete,
            on_settings=on_settings,
            on_layer_change=on_layer_change,
            on_long_press=on_long_press
        )

    def _on_expand_toggle(self, seg_index, is_expanded):
        """Handle segment expand/collapse"""
        self.segment_expanded.emit(seg_index, is_expanded)

    def _on_item_clicked(self, item):
        """Handle segment selection"""
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if item_data and item_data.item_type == 'segment':
            self.segment_clicked.emit(item_data.seg_index)

    def get_segment_item(self, seg_index):
        """Get the QListWidgetItem for a segment"""
        return self.segment_items.get(seg_index)


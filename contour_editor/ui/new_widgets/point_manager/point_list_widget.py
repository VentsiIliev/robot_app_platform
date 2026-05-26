from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtWidgets import QListWidget, QListWidgetItem

from .models import ListItemData
from .list_item_widgets import IndentedWidget, PointWidget
from ..styles import PRIMARY, PRIMARY_DARK, BORDER


class PointListWidget(QListWidget):
    point_clicked = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.point_items = []

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

    def add_anchor_point(self, seg_index, point_index, point):
        """Add an anchor point item to the list"""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 50))

        item_data = ListItemData(
            'point',
            seg_index=seg_index,
            point_index=point_index,
            point_type='anchor'
        )
        item.setData(Qt.ItemDataRole.UserRole, item_data)

        # Use PointWidget for modern styling
        point_label = f"P{point_index}"
        coordinates = f"({point.x():.1f}, {point.y():.1f})"
        point_widget = PointWidget(point_label, coordinates)

        indented_widget = IndentedWidget(point_widget, indent_level=2)

        self.addItem(item)
        self.setItemWidget(item, indented_widget)

        self.point_items.append(item)

    def add_control_point(self, seg_index, point_index, point):
        """Add a control point item to the list"""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 50))

        item_data = ListItemData(
            'point',
            seg_index=seg_index,
            point_index=point_index,
            point_type='control'
        )
        item.setData(Qt.ItemDataRole.UserRole, item_data)

        # Use PointWidget for modern styling
        point_label = f"C{point_index}"
        coordinates = f"({point.x():.1f}, {point.y():.1f})"
        point_widget = PointWidget(point_label, coordinates)

        indented_widget = IndentedWidget(point_widget, indent_level=2)

        self.addItem(item)
        self.setItemWidget(item, indented_widget)

        self.point_items.append(item)

    def _on_item_clicked(self, item):
        """Handle point selection"""
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if item_data and item_data.item_type == 'point':
            self.point_clicked.emit({
                'role': item_data.point_type,
                'seg_index': item_data.seg_index,
                'point_index': item_data.point_index
            })


from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtGui import QFont

from .styles import PRIMARY, BORDER

class LayerHeaderWidget(QWidget):
    def __init__(self, layer_name, button_widget, parent=None):
        super().__init__(parent)

        self.setStyleSheet(f"""
            QWidget {{
                background: white;
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
        """)
        self.setFixedHeight(70)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Layer name label with modern styling
        label = QLabel(layer_name)
        label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        label.setStyleSheet(f"""
            QLabel {{
                color: {PRIMARY};
                background: transparent;
                padding-left: 8px;
            }}
        """)

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(button_widget)

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])
    widget = LayerHeaderWidget("Layer 1", QWidget())
    widget.show()
    app.exec()
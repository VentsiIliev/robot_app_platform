from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QCheckBox

from pl_gui.settings.settings_view.styles import BORDER, PRIMARY, TEXT_COLOR


class CardCheckBox(QCheckBox):
    """Touch-sized checkbox with a clear checked indicator."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        font = self.font()
        font.setPointSize(11)
        self.setFont(font)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = (self.height() - 26) // 2
        box = QRect(0, top, 26, 26)
        painter.setPen(QPen(QColor(PRIMARY if self.isChecked() else BORDER), 1))
        painter.setBrush(QColor(PRIMARY if self.isChecked() else "white"))
        painter.drawRoundedRect(box, 5, 5)
        if self.isChecked():
            painter.setPen(QPen(QColor("white"), 3, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(6, top + 13, 11, top + 18)
            painter.drawLine(11, top + 18, 21, top + 7)
        painter.setPen(QColor(TEXT_COLOR if self.isEnabled() else BORDER))
        painter.setFont(self.font())
        painter.drawText(QRect(38, 0, self.width() - 38, self.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         self.text())

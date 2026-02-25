from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QPushButton, QGraphicsDropShadowEffect)

from src.settings.settings_view.styles import (
    PRIMARY, PRIMARY_DARK, PRIMARY_HOVER, TEXT_ON_PRIMARY,
    SECONDARY_BG, SECONDARY_HOVER, SECONDARY_PRESSED,
    TERTIARY_BG, TERTIARY_HOVER, TERTIARY_PRESSED, TERTIARY_TEXT,
    DISABLED_BG, SCROLLBAR_HANDLE_HOVER,
    SHADOW_PRIMARY, SHADOW_PRIMARY_HOVER,
)

from src.settings.settings_menu.icon_loader import load_icon


class MenuIcon(QPushButton):
    """Material Design 3 app icon with proper touch targets and visual feedback"""

    button_clicked = pyqtSignal(str)

    def __init__(self, icon_label, icon_path, icon_text="", callback=None, parent=None, qta_color=None):
        super().__init__(parent)
        self.icon_label = icon_label
        self.icon_path = icon_path
        self.icon_text = icon_text
        self.callback = callback
        # Optional color to use when rendering qtawesome icon strings specifically for mini icons
        self.qta_color = qta_color
        self._original_rect = None

        # Material Design touch target size (minimum 48dp)
        self.setFixedSize(112, 112)  # 112dp for comfortable touch interaction
        self.setup_ui()
        self.animation_manager = None

        # Connect callback if provided
        if self.callback is not None:
            self.button_clicked.connect(self.callback)

    def setup_ui(self):
        """Setup Material Design 3 styling with proper tokens"""

        # Material Design 3 filled button styling
        self.setStyleSheet(f"""
            QPushButton {{
                background: {PRIMARY};
                color: {TEXT_ON_PRIMARY};
                border: none;
                border-radius: 28px;
                font-size: 12px;
                font-weight: 500;
                font-family: 'Roboto', 'Segoe UI', sans-serif;
                text-align: center;
                padding: 8px;
            }}
            QPushButton:hover {{
                background: {PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background: {PRIMARY_DARK};
            }}
            QPushButton:disabled {{
                background: {DISABLED_BG};
                color: {SCROLLBAR_HANDLE_HOVER};
            }}
        """)

        # Material Design elevation shadow (level 1)
        try:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(12)
            shadow.setColor(QColor(*SHADOW_PRIMARY))
            shadow.setOffset(0, 2)
            self.setGraphicsEffect(shadow)
        except Exception:
            pass

        # Setup icon and text with Material Design principles
        self.setup_icon_content()

        # Material Design tooltip
        self.setToolTip(self.icon_label)

    def setup_icon_content(self):
        """Setup icon content following Material Design icon guidelines"""
        icon_size = int(self.width() * 0.5)
        size = QSize(icon_size, icon_size)

        icon = load_icon(self.icon_path, color=self.qta_color, size=size)
        if icon and not icon.isNull():
            self.setIcon(icon)
            self.setIconSize(size)
            self.setText("")
            return

        self.setup_fallback_text()

    def setup_fallback_text(self):
        """Setup fallback text with Material Design typography"""

        # Use emoji or abbreviation for better visual representation
        if self.icon_text and self.icon_text != " No text and icon provided":
            display_text = self.icon_text
        else:
            # Create abbreviation from app name (Material Design pattern)
            words = self.icon_label.split()
            if len(words) >= 2:
                display_text = ''.join(word[0].upper() for word in words[:2])
            else:
                display_text = self.icon_label[:2].upper()

        self.setText(display_text)

        # Adjust font size based on text length for optimal readability
        if len(display_text) <= 2:
            font_size = 18  # Larger for abbreviations
        else:
            font_size = 14  # Smaller for longer text

        # Update stylesheet for text-only display
        self.setStyleSheet(self.styleSheet() + f"""
            QPushButton {{
                font-size: {font_size}px;
                font-weight: 500;
                letter-spacing: 0.5px;
            }}
        """)

    def enterEvent(self, event):
        """Material Design hover state"""
        super().enterEvent(event)

        # Update shadow for hover state (Material Design elevation change)
        try:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(16)
            shadow.setColor(QColor(*SHADOW_PRIMARY_HOVER))
            shadow.setOffset(0, 4)
            self.setGraphicsEffect(shadow)
        except Exception:
            pass

    def leaveEvent(self, event):
        """Material Design normal state restoration"""
        super().leaveEvent(event)

        # Restore normal shadow
        try:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(12)
            shadow.setColor(QColor(*SHADOW_PRIMARY))
            shadow.setOffset(0, 2)
            self.setGraphicsEffect(shadow)
        except Exception:
            pass

    def mousePressEvent(self, event):
        """Material Design press interaction"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._original_rect = self.geometry()
            if self.animation_manager is not None:
                self.animation_manager.create_button_press_animation()
            self.button_clicked.emit(self.icon_label)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Material Design release interaction"""
        if self.animation_manager is not None:
            if event.button() == Qt.MouseButton.LeftButton and self._original_rect:
                self.animation_manager.create_button_release_animation(self._original_rect)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """Custom paint event for Material Design visual consistency"""
        super().paintEvent(event)

    def sizeHint(self):
        """Material Design size hint"""
        return QSize(112, 112)  # Consistent Material Design touch target

    def minimumSizeHint(self):
        """Minimum size following Material Design guidelines"""
        return QSize(48, 48)  # Material Design minimum touch target

    def set_icon_from_path(self, icon_path):
        """Update icon from new path with Material Design handling"""
        self.icon_path = icon_path
        self.setup_icon_content()

    def set_material_style(self, style_variant="primary"):
        """Apply different Material Design style variants"""

        style_variants = {
            "primary": {
                "background": PRIMARY,
                "hover": PRIMARY_HOVER,
                "pressed": PRIMARY_DARK,
                "text_color": TEXT_ON_PRIMARY
            },
            "secondary": {
                "background": SECONDARY_BG,
                "hover": SECONDARY_HOVER,
                "pressed": SECONDARY_PRESSED,
                "text_color": PRIMARY
            },
            "tertiary": {
                "background": TERTIARY_BG,
                "hover": TERTIARY_HOVER,
                "pressed": TERTIARY_PRESSED,
                "text_color": TERTIARY_TEXT
            }
        }

        if style_variant in style_variants:
            colors = style_variants[style_variant]

            self.setStyleSheet(f"""
                QPushButton {{
                    background: {colors['background']};
                    color: {colors['text_color']};
                    border: none;
                    border-radius: 28px;
                    font-size: 12px;
                    font-weight: 500;
                    font-family: 'Roboto', 'Segoe UI', sans-serif;
                    text-align: center;
                    padding: 8px;
                }}
                QPushButton:hover {{
                    background: {colors['hover']};
                }}
                QPushButton:pressed {{
                    background: {colors['pressed']};
                }}
                QPushButton:disabled {{
                    background: {DISABLED_BG};
                    color: {SCROLLBAR_HANDLE_HOVER};
                }}
            """)

    def set_material_size(self, size_variant="standard"):
        """Apply different Material Design size variants"""

        size_variants = {
            "compact": QSize(80, 80),
            "standard": QSize(112, 112),
            "large": QSize(144, 144)
        }

        if size_variant in size_variants:
            new_size = size_variants[size_variant]
            self.setFixedSize(new_size)

            # Update border radius proportionally
            radius = min(new_size.width(), new_size.height()) // 4

            current_style = self.styleSheet()
            # Update border-radius in stylesheet
            import re
            updated_style = re.sub(
                r'border-radius:\s*\d+px',
                f'border-radius: {radius}px',
                current_style
            )
            self.setStyleSheet(updated_style)

            # Update icon size proportionally
            if hasattr(self, 'icon') and not self.icon().isNull():
                icon_size = min(new_size.width(), new_size.height()) // 2
                self.setIconSize(QSize(icon_size, icon_size))

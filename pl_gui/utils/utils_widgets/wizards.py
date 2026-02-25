"""
Generic configurable wizard framework for step-by-step processes.

Provides base classes for creating wizards with:
- Configurable steps with title, subtitle, description, and optional images
- Selection steps with radio buttons or dropdowns
- Summary/review steps
- Material design buttons
- Customizable styling
"""

from pathlib import Path
from typing import Optional, List, Callable, Any
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QLabel,
    QRadioButton, QButtonGroup, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont, QIcon


from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton


try:
    from pl_gui.dashboard.resources.styles import WIZARD_IMAGE_PLACEHOLDER_STYLE, WIZARD_WARNING_LABEL_STYLE, STATUS_ERROR
except ImportError:
    try:
        from dashboard.styles import WIZARD_IMAGE_PLACEHOLDER_STYLE, WIZARD_WARNING_LABEL_STYLE, STATUS_ERROR
    except ImportError:
        WIZARD_IMAGE_PLACEHOLDER_STYLE = "QLabel { background-color: #F6F7FB; border: 2px dashed #E4E6F0; border-radius: 8px; }"
        WIZARD_WARNING_LABEL_STYLE = "font-size: 12px; padding: 10px; background-color: #fff3cd; border-radius: 5px;"
        STATUS_ERROR = "#d9534f"


@dataclass
class WizardStepConfig:
    """Configuration for a wizard step."""
    title: str
    subtitle: str
    description: str
    image_path: Optional[str] = None
    step_number: Optional[int] = None  # For "Step N:" prefix


class GenericWizardStep(QWizardPage):
    """Generic wizard step with title, subtitle, description, and optional image."""

    def __init__(self, config: WizardStepConfig):
        super().__init__()
        self.config = config

        # Set title with optional step number
        if config.step_number is not None:
            self.setTitle(f"Step {config.step_number}: {config.title}")
        else:
            self.setTitle(config.title)

        self.setSubTitle(config.subtitle)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()

        # Image section
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(200)
        self.image_label.setStyleSheet(WIZARD_IMAGE_PLACEHOLDER_STYLE)

        if self.config.image_path:
            pixmap = QPixmap(self.config.image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    400, 200,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setText("📷 Image Placeholder")
            font = QFont()
            font.setPointSize(14)
            self.image_label.setFont(font)

        layout.addWidget(self.image_label)

        # Description
        description_label = QLabel(self.config.description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet(
            "QLabel { margin: 15px 0; line-height: 1.5; font-size: 16px; }"
        )
        layout.addWidget(description_label)

        # Content layout for subclasses to add custom widgets
        self.content_layout = QVBoxLayout()
        layout.addLayout(self.content_layout)

        layout.addStretch()
        self.setLayout(layout)


class SelectionStep(GenericWizardStep):
    """Generic selection step with radio buttons."""

    def __init__(
        self,
        config: WizardStepConfig,
        options: List[str],
        selection_label: str = "Select an option:",
        empty_message: str = "No options available",
        empty_instructions: str = "Please configure options first"
    ):
        self.options = options
        self.selection_label = selection_label
        self.empty_message = empty_message
        self.empty_instructions = empty_instructions
        self.radio_buttons: List[QRadioButton] = []
        self.button_group: Optional[QButtonGroup] = None

        super().__init__(config)
        self._build_selection_ui()

    def _build_selection_ui(self):
        label = QLabel(self.selection_label)
        label.setStyleSheet("font-weight: bold; margin-top: 10px; font-size: 16px;")
        self.content_layout.addWidget(label)

        if not self.options:
            # Show empty state
            error_label = QLabel(f"⚠️ {self.empty_message}")
            error_label.setStyleSheet(
                f"color: {STATUS_ERROR}; font-weight: bold; font-size: 14px; padding: 10px;"
            )
            self.content_layout.addWidget(error_label)

            instruction_label = QLabel(self.empty_instructions)
            instruction_label.setStyleSheet(WIZARD_WARNING_LABEL_STYLE)
            instruction_label.setWordWrap(True)
            self.content_layout.addWidget(instruction_label)
            return

        # Create radio buttons
        self.button_group = QButtonGroup(self)
        for idx, option in enumerate(self.options):
            radio = QRadioButton(option)
            radio.setStyleSheet("font-size: 14px;")
            if idx == 0:
                radio.setChecked(True)
            self.button_group.addButton(radio, idx)
            self.radio_buttons.append(radio)
            self.content_layout.addWidget(radio)

    def get_selected_option(self) -> Optional[str]:
        """Get the currently selected option."""
        for radio in self.radio_buttons:
            if radio.isChecked():
                return radio.text()
        return self.radio_buttons[0].text() if self.radio_buttons else None


class SummaryStep(GenericWizardStep):
    """Generic summary/review step with HTML content."""

    def __init__(
        self,
        config: WizardStepConfig,
        summary_generator: Optional[Callable[[QWizard], str]] = None
    ):
        self.summary_generator = summary_generator
        super().__init__(config)
        self._build_summary_ui()

    def _build_summary_ui(self):
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(150)
        self.summary_text.setStyleSheet("font-size: 14px;")
        self.content_layout.addWidget(self.summary_text)

    def initializePage(self):
        """Called when the page is shown - generate summary dynamically."""
        if self.summary_generator:
            summary_html = self.summary_generator(self.wizard())
            self.summary_text.setHtml(summary_html)


class ConfigurableWizard(QWizard):
    """
    Generic configurable wizard base class.

    Usage:
        wizard = ConfigurableWizard(
            title="My Wizard",
            pages=[step1, step2, step3],
            icon_path="path/to/icon.ico",
            logo_path="path/to/logo.png",
            min_width=600,
            min_height=500
        )
    """

    def __init__(
        self,
        title: str,
        pages: List[QWizardPage],
        icon_path: Optional[str] = None,
        logo_path: Optional[str] = None,
        min_width: int = 600,
        min_height: int = 500,
        on_finish_callback: Optional[Callable[[Any], None]] = None,
        use_material_buttons: bool = True,
        parent=None
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(min_width, min_height)
        self.on_finish_callback = on_finish_callback

        # Set icon
        if icon_path and Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))

        # Set logo
        if logo_path and Path(logo_path).exists():
            logo_pixmap = QPixmap(logo_path)
            self.setPixmap(
                QWizard.WizardPixmap.LogoPixmap,
                logo_pixmap.scaled(
                    60, 60,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )

        # Add pages
        for page in pages:
            self.addPage(page)

        # Customize buttons if requested
        if use_material_buttons:
            self._customize_buttons()

        # Connect finish button
        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self._on_finish)

    def _customize_buttons(self):
        """Replace default buttons with MaterialButtons and explicitly wire actions."""
        button_actions = {
            QWizard.WizardButton.BackButton: self.back,
            QWizard.WizardButton.NextButton: self.next,
            QWizard.WizardButton.FinishButton: self.accept,  # ← explicit accept()
            QWizard.WizardButton.CancelButton: self.reject,  # ← explicit reject()
        }
        for button_type, action in button_actions.items():
            btn = self.button(button_type)
            if btn is None:
                continue
            new_btn = MaterialButton(btn.text())
            new_btn.clicked.connect(action)
            self.setButton(button_type, new_btn)

    def _on_finish(self):
        """Called when finish button is clicked."""
        if self.on_finish_callback:
            self.on_finish_callback(self)


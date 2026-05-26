import os
import sys

# CRITICAL: Add package root to sys.path BEFORE any other imports
# This allows both relative imports (package mode) and absolute imports (standalone mode)
current_file = os.path.abspath(__file__)
core_dir = os.path.dirname(current_file)  # core/
contour_editor_dir = os.path.dirname(core_dir)  # contour_editor/
src_dir = os.path.dirname(contour_editor_dir)  # src/

# Add src to path so 'contour_editor' can be imported
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import numpy as np
from PyQt6.QtCore import (
    pyqtSignal, QSize, QEventLoop, QPointF, Qt
)
from PyQt6.QtWidgets import QFrame, QWidget, QApplication, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout
from shapely import Polygon, LineString

# Now import from package - will work in both standalone and package mode
from contour_editor.models.bezier_segment_manager import BezierSegmentManager
from contour_editor.services.contour_processing_service import ContourProcessingService
from contour_editor.core.editor_with_toolbar import ContourEditorWithBottomToolBar
from contour_editor.ui.new_widgets.LayerAndValueInputDialog import LayerAndValueInputDialog
from contour_editor.ui.new_widgets.point_manager.point_manager_widget import PointManagerWidget
from contour_editor.ui.new_widgets.SlidingPanel import SlidingPanel
from contour_editor.persistence.utils.utils import shrink_contour_points, generate_spray_pattern
# from contour_editor.ui.new_widgets.TopbarWidget import TopBarWidget
from contour_editor.ui.new_widgets.TopbarWidget import TopBarWidget
from contour_editor.persistence.providers import (
    DialogProvider,
    AdditionalFormProvider,
    AdditionalFormBehaviorProvider,
)


class MainApplicationFrame(QFrame):
    capture_requested = pyqtSignal()
    update_camera_feed_requested = pyqtSignal()
    save_requested = pyqtSignal(object)  # Emits form_data dict or None
    execute_requested = pyqtSignal(object)  # Signal to request execution
    start_requested = pyqtSignal()  # Signal when start/execute button is pressed
    capture_data_received = pyqtSignal(dict, bool)  # Signal when capture data is received (data, close_contour)
    additional_form_created = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        # State management
        self.current_view = "point_manager"  # "point_manager" or "additional_form"
        self.initUI()

    def initUI(self):
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)

        self.contourEditor = ContourEditorWithBottomToolBar(None, image_path="imageDebug.png", data=None)
        self.contourEditor.update_camera_feed_requested.connect(self.update_camera_feed_requested.emit)

        # Initialize ContourProcessingService with the actual editor's manager
        actual_editor = self.contourEditor.editor_with_rulers.editor

        self.contour_processing_service = ContourProcessingService(actual_editor.manager)

        # Top bar widget
        # self.topbar = TopBarWidget(self.contourEditor, None)
        self.topbar = TopBarWidget()
        self.topbar.save_requested.connect(self.on_first_save_clicked)
        self.topbar.capture_requested.connect(self.capture_requested.emit)
        self.topbar.start_requested.connect(self.onStart)
        self.topbar.generate_pattern_requested.connect(self.generateLineGridPattern)
        # self.topbar.offset_requested.connect(self.shrink)
        self.topbar.undo_requested.connect(self.on_undo)
        self.topbar.redo_requested.connect(self.on_redo)
        self.topbar.preview_requested.connect(self.show_preview)
        self.topbar.multi_select_mode_requested.connect(self.on_multi_select_mode_requested)
        self.topbar.remove_points_requested.connect(self.contourEditor.remove_selected_points)
        self.topbar.settings_requested.connect(self.contourEditor.open_settings_dialog)
        self.topbar.tools_requested.connect(self.contourEditor.show_tools_menu)
        mainLayout.addWidget(self.topbar)

        # Horizontal layout for the main content
        horizontal_widget = QWidget()
        horizontalLayout = QHBoxLayout(horizontal_widget)
        horizontalLayout.setContentsMargins(0, 0, 0, 0)

        horizontalLayout.addWidget(self.contourEditor, stretch=1)

        # Create the right panel widgets
        self.pointManagerWidget = PointManagerWidget(self.contourEditor, self.parent)
        self.pointManagerWidget.point_selected_signal.connect(lambda point_info:self.contourEditor.selection_manager.set_single_selection_from_dict(point_info))
        self.topbar.point_manager = self.pointManagerWidget
        self.contourEditor.point_manager_widget = self.pointManagerWidget

        # Set point manager widget reference in the settings manager for Ctrl+G shortcut
        self.contourEditor.settings_manager.set_point_manager_widget(self.pointManagerWidget)

        self.pointManagerWidget.setFixedWidth(400)

        # Wrap point manager in a sliding panel
        self.sliding_panel = SlidingPanel(self.pointManagerWidget, parent=horizontal_widget)

        # Additional data form (can be injected via provider)
        self.additional_data_form = None # will be created on demand

        # Add a sliding panel to the layout (no stretch - it will use its size hints)
        horizontalLayout.addWidget(self.sliding_panel, stretch=0)

        mainLayout.addWidget(horizontal_widget)


    def on_capture_requested(self):
        # clear the point manager and contour editor before capturing
        self.pointManagerWidget.refresh_points()
        self.contourEditor.reset_editor()

    def show_preview(self):
        self.contourEditor.save_robot_path_to_txt("preview.txt", samples_per_segment=5)
        self.contourEditor.plot_robot_path("preview.txt")

    def reset_zoom(self):
        if not self.contourEditor:
            raise ValueError("Contour editor is not set.")


        self.contourEditor.editor_with_rulers.editor.viewport_controller.reset_zoom()

    def on_redo(self):
        if not self.contourEditor:
            return

        from contour_editor.services.commands import CommandHistory
        from contour_editor.core.event_bus import EventBus

        history = CommandHistory.get_instance()

        if history.can_redo():
            # Use CommandHistory for segment-level operations
            history.redo()
            EventBus.get_instance().redo_executed.emit()
        else:
            # Fall back to manager's snapshot redo for point-level operations
            try:
                self.contourEditor.manager.redo()
                self.pointManagerWidget.refresh_points()
            except Exception:
                return

        # Qt's standard update mechanism - no forced repaints
        self.contourEditor.editor.update()
        self.contourEditor.update()

    def on_undo(self):
        if not self.contourEditor:
            return

        from contour_editor.services.commands import CommandHistory
        from contour_editor.core.event_bus import EventBus

        history = CommandHistory.get_instance()

        if history.can_undo():
            # Use CommandHistory for segment-level operations
            history.undo()
            EventBus.get_instance().undo_executed.emit()
        else:
            # Fall back to manager's snapshot undo for point-level operations
            try:
                self.contourEditor.manager.undo()
                self.pointManagerWidget.refresh_points()
            except Exception:
                return

        # Qt's standard update mechanism - no forced repaints
        self.contourEditor.editor.update()
        self.contourEditor.update()

    def on_multi_select_mode_requested(self):
        """Handle multi-select mode toggle request from toolbar"""
        if not self.contourEditor:
            print("Error: Contour editor is not set.")
            return

        # Toggle multi-select mode in the editor
        is_active = self.contourEditor.toggle_multi_select_mode()

        # Update toolbar UI to reflect the new state
        self.topbar.update_multi_select_ui(is_active)

    def set_form_submit_callback(self, callback):
        """
        Set custom callback for form submission.

        Domain-agnostic method to override the default form submit behavior.

        Note: Usually you don't need this - just connect to save_requested signal.
        This is for advanced use cases where you want to override the default behavior.

        Args:
            callback: Function to call when form is submitted.
                     Should accept form_data dict and return (success: bool, message: str)
        """
        if self.additional_data_form:
            self.additional_data_form.onSubmitCallBack = callback
            print("[MainApplicationFrame] Custom form submit callback set")

    def set_verification_contours(self, contours) -> None:
        self.contourEditor.editor_with_rulers.editor.set_verification_contours(contours)

    def clear_verification_contours(self) -> None:
        self.contourEditor.editor_with_rulers.editor.clear_verification_contours()

    def shrink(self):
        contour_points = self.contour_processing_service.get_main_contour_points()

        if contour_points is None:
            DialogProvider.get().show_info(
                self,
                "No Contour",
                "No main contour found.",
                "No main contour found."
            )
            return

        shrink_dialog = LayerAndValueInputDialog(
            dialog_title="Shrink Contour",
            layer_label="Select layer for shrunk contour:",
            input_labels=["Enter shrink value (mm):"],
            input_defaults=[5],
            input_ranges=[(1, 50)],
            layer_options=self.contourEditor.manager.get_available_layer_names(),
        )

        shrink_dialog.show()
        loop = QEventLoop()
        shrink_dialog.finished.connect(loop.quit)
        loop.exec()

        if shrink_dialog.result() != QDialog.DialogCode.Accepted:
            print("Shrink operation canceled.")
            return

        vals = shrink_dialog.get_values()
        if not vals or len(vals) < 2:
            print("Invalid dialog return values.")
            return

        selected_layer = vals[0]
        try:
            shrink_amount = float(vals[1])
        except Exception:
            print("Invalid shrink amount provided.")
            return

        if shrink_amount <= 0:
            print("Shrink amount must be positive.")
            return

        print(f"Shrinking contour by: {shrink_amount} to layer: {selected_layer}")

        segment_point_lists = self.contour_processing_service.shrink_contour(contour_points, shrink_amount)

        if segment_point_lists is None or len(segment_point_lists) == 0:
            print("Shrink amount too large — polygon disappeared or invalid result!")
            return

        self.contour_processing_service.create_segments_from_points(segment_point_lists, selected_layer)

        self.contourEditor.update()
        self.pointManagerWidget.refresh_points()
        print(f"Added shrunk contour inward by {shrink_amount} units as new segments in {selected_layer} layer.")

    def generateLineGridPattern(self):
        """Generate zig-zag lines aligned to the main contour using minimum area bounding box orientation."""
        pattern_layers = self.contourEditor.manager.get_pattern_layer_names()
        if not pattern_layers:
            DialogProvider.get().show_info(
                self,
                "No Pattern Layers",
                "This editor is configured without pattern layers.",
                "This editor is configured without pattern layers."
            )
            return

        contour_points = self.contour_processing_service.get_main_contour_points()

        if contour_points is None:
            DialogProvider.get().show_info(
                self,
                "No Contour",
                "No main contour found.",
                "No main contour found."
            )
            return

        dialog = LayerAndValueInputDialog(
            dialog_title="Spray Pattern Settings",
            layer_label="Select layer type:",
            input_labels=["Line grid spacing (mm):", "Shrink offset (mm):"],
            input_defaults=[20, 0.0],
            input_ranges=[(1, 1000), (0.0, 50.0)],
            layer_options=pattern_layers,
        )
        dialog.show()

        loop = QEventLoop()
        dialog.finished.connect(loop.quit)
        loop.exec()

        if dialog.result() != QDialog.DialogCode.Accepted:
            print("Zig-zag pattern generation cancelled by user.")
            return

        selected_layer, spacing, shrink_offset = dialog.get_values()

        # Clear segments in the selected layer (modify in-place to preserve reference)
        segments_to_keep = [
            s for s in self.contourEditor.manager.get_segments()
            if getattr(s.layer, "name", "") != selected_layer
        ]
        self.contourEditor.manager.segments.clear()
        self.contourEditor.manager.segments.extend(segments_to_keep)
        self.contourEditor.update()

        if shrink_offset < 1:
            shrink_offset = 1

        zigzag_segments = self.contour_processing_service.generate_spray_pattern(
            contour_points, spacing, shrink_offset
        )

        if zigzag_segments is None or len(zigzag_segments) == 0:
            print("Failed to generate spray pattern")
            return

        if self.contourEditor.manager.is_fill_layer_name(selected_layer):
            self.contour_processing_service.create_fill_pattern(
                zigzag_segments, selected_layer, contour_points
            )
        else:
            self.contour_processing_service.create_contour_pattern(
                zigzag_segments, selected_layer
            )

        self.contourEditor.update()
        self.pointManagerWidget.refresh_points()
        print("Generated zig-zag grid aligned to main contour.")

    def on_first_save_clicked(self):
        """Handle the first save button click - switch from point manager to additional data form"""
        if self.current_view == "point_manager":

            if self.additional_data_form is None:
                # Try to create form using provider
                self.additional_data_form = AdditionalFormProvider.get().create_form(parent=self)

                if self.additional_data_form is not None:
                    # Form was successfully created via provider
                    self.additional_data_form.setFixedWidth(400)


                    def on_form_submit(form_data):
                        """Callback when form is submitted - just emit the form data"""
                        print(f"✅ Form submitted with data: {list(form_data.keys())}")
                        self.save_requested.emit(form_data)
                        return True, "Form data emitted"
                    
                    self.additional_data_form.onSubmitCallBack = on_form_submit
                    print("✅ Form submit callback connected")

                    # Connect data_submitted signal if it exists (backward compatibility)
                    if hasattr(self.additional_data_form, 'data_submitted'):
                        self.additional_data_form.data_submitted.connect(
                            lambda data: self.save_requested.emit(data)
                        )
                    AdditionalFormBehaviorProvider.get().apply_behaviors(self.additional_data_form, self)
                    self.additional_form_created.emit(self.additional_data_form)
                    print("[ContourEditor] Additional data form successfully created via provider")

            # Try to create form using AdditionalFormProvider
            if self.additional_data_form is not None:
                if hasattr(self.contourEditor, 'data') and self.contourEditor.data is not None:
                    # prefill form with existing data
                    self.additional_data_form.clear()
                    self.additional_data_form.prefill_form(self.contourEditor.data)
                else:
                    # clear the form in case it has old data
                    self.additional_data_form.clear()
                    print("No data to prefill the form.")

                self.sliding_panel.replace_content_widget(self.additional_data_form)
                # Update the save button callback to handle data saving
                self.topbar.save_requested.disconnect()
                self.topbar.save_requested.connect(self.on_data_save_clicked)
                self.current_view = "additional_form"
                print("Switched to additional data form")
            else:
                # Show the message that this functionality requires form provider
                DialogProvider.get().show_info(
                    self,
                    "Feature Not Available",
                    "Additional data form is not configured.",
                    "This feature requires a form to be injected via provider pattern."
                )
                print("Additional data form not available - feature disabled")

        # if the sliding panel is hidden, show it
        if not self.sliding_panel.is_visible:
            self.sliding_panel.toggle_panel()

    def onStart(self):
        """
        Handle start/execute button press - emit signal with complete data package.

        Domain-agnostic - collects both form and editor data, emits start_requested and execute_requested signals.
        Applications should connect to these signals and implement their own execution logic.

        Emits:
            start_requested signal (no data)
            execute_requested signal with dict containing:
                - 'form_data': Dictionary from the form (if form exists), or empty dict
                - 'editor_data': ContourEditorData from the editor
        """
        print("[MainApplicationFrame] Start/Execute requested - collecting complete data")

        try:
            # Get form data if form exists, ensure it's a dict
            if self.additional_data_form:
                form_data = self.additional_data_form.get_data()
                # Handle None or non-dict returns
                if form_data is None or not isinstance(form_data, dict):
                    form_data = {}
                print(f"[MainApplicationFrame] Form data collected: {list(form_data.keys())}")
            else:
                form_data = {}
                print("[MainApplicationFrame] No form available")

            # Export editor data (domain-agnostic ContourEditorData)
            from contour_editor.persistence.data.editor_data_model import ContourEditorData
            editor_data = ContourEditorData.from_manager(self.contourEditor.manager)

            # Create complete data package
            complete_package = {
                'form_data': form_data,
                'editor_data': editor_data
            }

            stats = editor_data.get_statistics()
            print(f"[MainApplicationFrame] Editor data: {stats['total_segments']} segments, {stats['total_points']} points")

            # Emit signals
            self.start_requested.emit()
            self.execute_requested.emit(complete_package)
            print("✅ Execute requested signal emitted with complete data package")

        except Exception as e:
            print(f"❌ Error collecting data for execution: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to collect data for execution: {e}")

    def on_data_save_clicked(self):
        """
        Handle save button click - collect form data AND editor data, emit complete package.

        Domain-agnostic - collects both form and editor data, emits save_requested signal.
        Applications should connect to this signal and implement their own save logic.

        Emits:
            save_requested signal with dict containing:
                - 'form_data': Dictionary from the form (if form exists)
                - 'editor_data': ContourEditorData from the editor
        """
        try:
            # Get form data if form exists
            form_data = self.additional_data_form.get_data() if self.additional_data_form else {}
            print(f"[MainApplicationFrame] Save requested with form data: {list(form_data.keys())}")

            # Export editor data (domain-agnostic ContourEditorData)
            from contour_editor.persistence.data.editor_data_model import ContourEditorData
            editor_data = ContourEditorData.from_manager(self.contourEditor.manager)

            # Create complete data package
            complete_package = {
                'form_data': form_data,
                'editor_data': editor_data
            }

            stats = editor_data.get_statistics()
            print(f"[MainApplicationFrame] Editor data exported: {stats['total_segments']} segments, {stats['total_points']} points")

            # Emit complete package - handler will implement save logic
            self.save_requested.emit(complete_package)

            # Step 6: Reset UI back to point manager after successful emitting
            self.contourEditor.camera_feed_update_timer.start()
            self.contourEditor.reset_editor()
            self.pointManagerWidget.refresh_points()
            self.sliding_panel.replace_content_widget(self.pointManagerWidget)

            # Restore save button to show form again
            try:
                self.topbar.save_requested.disconnect()
            except Exception:
                pass
            self.topbar.save_requested.connect(self.on_first_save_clicked)

            self.current_view = "point_manager"
            print("✅ Switched back to point manager after emitting save signal")

        except Exception as e:
            print(f"❌ Error preparing data: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to prepare data: {e}")

    def set_image(self, image):
        self.contourEditor.set_image(image)

    def init_contours(self, contours):
        """
        Initialize contours using legacy format.

        DEPRECATED: Use load_capture_data() for new code.
        """
        print("in contour editor.py")
        self.contourEditor.initContour(contours)

    def load_capture_data(self, capture_data, close_contour=True):
        """
        Load camera capture data into the editor.

        Domain-agnostic - emits capture_data_received signal.
        Applications should connect to this signal and implement their own capture handling.

        Args:
            capture_data: Dictionary with keys:
                - "contours": numpy array or list of contours
                - "image": optional image data
                - "height": optional height measurement
            close_contour: Whether to close the contour

        Returns:
            None (signal-based, no direct return)
        """
        print(f"[MainApplicationFrame] Capture data received - emitting capture_data_received signal")
        self.capture_data_received.emit(capture_data, close_contour)

    def resizeEvent(self, event):
        """Resize content and side menu dynamically."""
        super().resizeEvent(event)
        new_width = self.width()

        # Guard against resizeEvent being called before initialization completes
        if not hasattr(self, 'topbar'):
            return

        # # Adjust icon sizes of the sidebar buttons
        # icon_size = int(new_width * 0.05)  # 5% of the new window width
        # for button in self.topbar.buttons:
        #     button.setIconSize(QSize(icon_size, icon_size))

        if self.additional_data_form is not None:

            if hasattr(self.additional_data_form, 'buttons'):
                for button in self.additional_data_form.buttons:
                    button.setIconSize(QSize(icon_size, icon_size))

            # Resize the icons in the labels
            if hasattr(self.additional_data_form, 'icon_widgets'):
                for label, original_pixmap in self.additional_data_form.icon_widgets:
                    scaled_pixmap = original_pixmap.scaled(
                        int(icon_size / 2), int(icon_size / 2),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    label.setPixmap(scaled_pixmap)

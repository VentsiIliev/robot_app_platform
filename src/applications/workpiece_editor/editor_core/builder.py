"""
Workpiece Editor Builder
Wraps ContourEditorBuilder and adds workpiece-specific functionality.
This builder automatically configures workpiece-specific handlers, adapters,
and managers.
"""

from typing import Optional, Callable, Any
from contour_editor import ContourEditorBuilder
from contour_editor.core.main_frame import MainApplicationFrame
from .managers.workpiece_manager import WorkpieceManager
from .handlers import StartHandler, CaptureHandler


class WorkpieceEditorBuilder:
    """
    Builder for configuring and creating a workpiece-aware ContourEditor instance.
    This builder wraps ContourEditorBuilder and automatically injects
    workpiece-specific dependencies (WorkpieceAdapter, WorkpieceManager, handlers).
    Example:
        editor = (WorkpieceEditorBuilder()
                  .with_segment_manager(MySegmentManager)
                  .with_settings(my_config, my_provider)
                  .with_form(my_form_factory)
                  .on_save_workpiece(my_save_handler)
                  .on_capture_workpiece(my_capture_handler)
                  .build())
    """

    def __init__(self):
        self._base_builder = ContourEditorBuilder()
        self._editor: Optional[MainApplicationFrame] = None
        self._workpiece_manager: Optional[WorkpieceManager] = None
        self._start_handler: Optional[StartHandler] = None
        self._capture_handler: Optional[CaptureHandler] = None

    def with_parent(self, parent):
        """Set parent widget"""
        self._base_builder.with_parent(parent)
        return self

    def with_segment_manager(self, manager_class):
        """Configure segment manager backend (REQUIRED)"""
        self._base_builder.with_segment_manager(manager_class)
        return self

    def with_settings(self, config, provider=None):
        """Configure segment settings (optional)"""
        self._base_builder.with_settings(config, provider)
        return self

    def with_form(self, form_factory):
        """Configure workpiece form (optional)"""
        self._base_builder.with_form(form_factory)
        return self

    def with_widgets(self, widget_factory):
        """Configure custom widgets (optional)"""
        self._base_builder.with_widgets(widget_factory)
        return self

    def on_save(self, callback: Callable[[dict], None]):
        """
        Set callback for save events.
        Callback receives merged form data + workpiece contour data.
        """
        self._base_builder.on_save(callback)
        return self

    def on_capture(self, callback: Callable[[], None]):
        """Set callback for capture events"""
        self._base_builder.on_capture(callback)
        return self

    def on_execute(self, callback: Callable[[Any], None]):
        """Set callback for execute events"""
        self._base_builder.on_execute(callback)
        return self

    def on_update_camera_feed(self, callback: Callable[[], None]):
        """Set callback for camera feed update events"""
        self._base_builder.on_update_camera_feed(callback)
        return self

    def build(self) -> MainApplicationFrame:
        """Build and return configured editor instance with workpiece support"""
        # Build the base editor
        self._editor = self._base_builder.build()
        # Inject WorkpieceManager (wraps the editor)
        self._workpiece_manager = WorkpieceManager(self._editor.contourEditor.editor_with_rulers.editor)
        self._editor.contourEditor.editor_with_rulers.editor.workpiece_manager = self._workpiece_manager
        if self._editor.contourEditor.editor_with_rulers.editor.workpiece_manager is not None:
            print(f"Set workpiece manager OK")
        else:
            print(f"Failed to set workpiece manager OK")
        # Create and connect StartHandler for workpiece-specific start logic
        self._start_handler = StartHandler(self._editor)
        self._editor.start_requested.connect(self._start_handler.handle_start)

        # Create and connect CaptureHandler for workpiece-specific capture logic
        self._capture_handler = CaptureHandler(self._editor)
        self._editor.capture_data_received.connect(self._capture_handler.handle_capture_data)

        print("✅ Workpiece Editor built successfully with WorkpieceManager, StartHandler, and CaptureHandler")
        return self._editor

    def load_workpiece(self, workpiece):
        """
        Load a workpiece into the editor.
        Must be called after build().
        """
        if not self._workpiece_manager:
            raise RuntimeError("Cannot load workpiece before building editor. Call build() first.")
        return self._workpiece_manager.load_workpiece(workpiece)

    def export_workpiece_data(self) -> dict:
        """
        Export current editor state as workpiece-compatible data.
        Must be called after build().
        """
        if not self._workpiece_manager:
            raise RuntimeError("Cannot export workpiece data before building editor. Call build() first.")
        return self._workpiece_manager.export_to_workpiece_data()

    def get_workpiece_manager(self) -> Optional[WorkpieceManager]:
        """Get the WorkpieceManager instance (available after build())"""
        return self._workpiece_manager




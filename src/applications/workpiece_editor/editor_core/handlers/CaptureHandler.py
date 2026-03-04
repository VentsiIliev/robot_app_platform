"""
CaptureHandler - Handles workpiece-specific capture data loading
This handler implements workpiece-specific capture logic using CaptureDataHandler.
It's connected to the capture_data_received signal.
"""
from PyQt6.QtCore import QObject
from .CaptureDataHandler import CaptureDataHandler
class CaptureHandler(QObject):
    """
    Handles workpiece-specific capture data loading.
    This class should be instantiated and connected to MainApplicationFrame's
    capture_data_received signal in workpiece-aware applications.
    """
    def __init__(self, editor_frame, parent=None):
        super().__init__(parent)
        self.editor_frame = editor_frame
    def handle_capture_data(self, capture_data, close_contour=True):
        """
        Handle capture data using workpiece-specific logic.
        Uses CaptureDataHandler to process the capture data and load it
        into the editor using the workpiece manager.
        Args:
            capture_data: Dictionary with capture data
            close_contour: Whether to close the contour
        """
        print("[CaptureHandler] Handling capture data with workpiece logic")
        try:
            if not hasattr(self.editor_frame.contourEditor, 'workpiece_manager'):
                print("[CaptureHandler] Error: workpiece_manager not available")
                return None
            # Use CaptureDataHandler to process the data
            editor_data = CaptureDataHandler.handle_capture_data(
                workpiece_manager=self.editor_frame.contourEditor.workpiece_manager,
                capture_data=capture_data,
                close_contour=close_contour
            )
            print(f"[CaptureHandler] Capture data loaded successfully")
            return editor_data
        except Exception as e:
            print(f"[CaptureHandler] Error handling capture data: {e}")
            import traceback
            traceback.print_exc()
            return None

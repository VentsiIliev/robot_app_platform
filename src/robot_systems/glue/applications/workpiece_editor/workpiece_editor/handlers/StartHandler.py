"""
StartHandler - Handles workpiece start/execution logic
This handler implements workpiece-specific start logic that was previously
in main_frame.py. It's connected to the start_requested signal.
"""
from PyQt6.QtWidgets import QMessageBox, QApplication
from PyQt6.QtCore import QObject
from typing import Optional
class StartHandler(QObject):
    """
    Handles workpiece-specific start/execution logic.
    This class should be instantiated and connected to MainApplicationFrame's
    start_requested signal in workpiece-aware applications.
    """
    def __init__(self, editor_frame, parent=None):
        super().__init__(parent)
        self.editor_frame = editor_frame
    def handle_start(self):
        """
        Handle start button press - implement workpiece-specific logic.
        This includes:
        - Validating glue types
        - Creating mock workpiece data
        - Merging with contour data
        - Emitting execute signal
        """
        print("[StartHandler] Handling start request with workpiece logic")
        # Step 1: Request and validate glue types
        registered_glue_types = self._fetch_glue_types()
        if not registered_glue_types:
            QMessageBox.critical(
                self.editor_frame,
                "No Glue Types Configured",
                "No glue types are registered in the system!\n\n"
                "Please configure glue types in:\n"
                "1. Glue Cell Settings (Settings → Glue Cells)\n"
                "2. Assign types to cells with motor addresses\n\n"
                "Cannot start execution without glue type configuration.",
                QMessageBox.StandardButton.Ok
            )
            print("[StartHandler] Execution aborted: No glue types registered")
            return
        # Step 2: Validate segment glue types
        invalid_segments = self._validate_segment_glue_types(registered_glue_types)
        if invalid_segments:
            error_message = "Invalid glue type configuration found:\n\n"
            error_message += "\n".join(invalid_segments)
            error_message += f"\n\nRegistered glue types: {', '.join(registered_glue_types)}"
            error_message += "\n\nPlease fix segment settings before starting execution."
            QMessageBox.critical(
                self.editor_frame,
                "Invalid Segment Configuration",
                error_message,
                QMessageBox.StandardButton.Ok
            )
            print(f"[StartHandler] Execution aborted: {len(invalid_segments)} invalid segment(s)")
            return
        print(f"[StartHandler] ✅ All segments have valid glue types")
        # Step 3: Prepare workpiece data
        try:
            workpiece_data = self._prepare_workpiece_data(registered_glue_types[0])
            # Step 4: Create workpiece and emit execute signal
            from workpiece_editor.models import WorkpieceFactory
            wp = WorkpieceFactory.create_workpiece(workpiece_data)
            print(f"[StartHandler] Workpiece created: {wp}")
            # Emit execute signal
            self.editor_frame.execute_requested.emit(wp)
        except Exception as e:
            QMessageBox.critical(
                self.editor_frame,
                "Workpiece Creation Failed",
                f"Failed to create workpiece: {e}"
            )
            import traceback
            traceback.print_exc()
    def _fetch_glue_types(self):
        """Fetch registered glue types from editor"""
        print("[StartHandler] Requesting glue types...")
        if not hasattr(self.editor_frame, 'contourEditor'):
            return []
        contour_editor = self.editor_frame.contourEditor
        if hasattr(contour_editor, 'editor_with_rulers'):
            if hasattr(contour_editor.editor_with_rulers, 'editor'):
                editor = contour_editor.editor_with_rulers.editor
                if hasattr(editor, 'fetch_glue_types_requested'):
                    editor.fetch_glue_types_requested.emit()
                    QApplication.processEvents()
                    glue_types = editor.glue_type_names
                    print(f"[StartHandler] Registered glue types: {glue_types}")
                    return glue_types
        return []
    def _validate_segment_glue_types(self, registered_glue_types):
        """Validate that all segments have valid glue types"""
        segments = self.editor_frame.contourEditor.manager.get_segments()
        invalid_segments = []
        for idx, segment in enumerate(segments):
            segment_settings = segment.settings if hasattr(segment, 'settings') and segment.settings else {}
            segment_glue_type = segment_settings.get('Glue Type', None)
            if not segment_glue_type:
                invalid_segments.append(f"Segment {idx}: No glue type set")
            elif segment_glue_type not in registered_glue_types:
                invalid_segments.append(f"Segment {idx}: Invalid glue type '{segment_glue_type}'")
        return invalid_segments
    def _prepare_workpiece_data(self, default_glue_type):
        """Prepare complete workpiece data by merging form data with contour data"""
        from ..adapters.workpiece_adapter import WorkpieceAdapter
        # Create mock form data (in real app, this would come from actual form)
        mock_data = {
            "workpieceId": "WP123",
            "name": "Test Workpiece",
            "description": "Sample description",
            "offset": "10,20,30",
            "height": "50",
            "glueQty": "100",
            "sprayWidth": "5",
            "toolId": "0",
            "gripperId": "0",
            "glueType": default_glue_type,
            "program": "Trace",
            "material": "Material1",
            "contourArea": "1000",
        }
        # Add pickup point if set
        if hasattr(self.editor_frame.contourEditor, 'pickup_point'):
            if self.editor_frame.contourEditor.pickup_point is not None:
                pickup_point_str = f"{self.editor_frame.contourEditor.pickup_point.x():.2f},{self.editor_frame.contourEditor.pickup_point.y():.2f}"
                mock_data["pickup_point"] = pickup_point_str
                print(f"[StartHandler] Pickup point included: {pickup_point_str}")
        # Get contour data from editor using workpiece manager
        if hasattr(self.editor_frame.contourEditor, 'workpiece_manager'):
            editor_data = self.editor_frame.contourEditor.workpiece_manager.export_editor_data()
            contour_data = WorkpieceAdapter.to_workpiece_data(editor_data)
            # Validate spray pattern
            spray_pattern = contour_data.get("spray_pattern", {})
            if not self._has_valid_patterns(spray_pattern):
                raise ValueError("No valid contour or fill patterns found!")
            # Merge mock form data with contour data
            complete_data = {**mock_data, **contour_data}
            return complete_data
        else:
            raise RuntimeError("Workpiece manager not available")
    def _has_valid_patterns(self, spray_pattern):
        """Check if spray pattern has valid contour or fill data"""
        def has_valid_contours(contour_list):
            if not contour_list or len(contour_list) == 0:
                return False
            for item in contour_list:
                if isinstance(item, dict) and 'contour' in item:
                    contour = item['contour']
                    if contour.size > 0 and len(contour) > 0:
                        return True
            return False
        contour_data = spray_pattern.get("Contour", [])
        fill_data = spray_pattern.get("Fill", [])
        return has_valid_contours(contour_data) or has_valid_contours(fill_data)

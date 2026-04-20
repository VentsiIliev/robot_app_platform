
"""
WorkpieceManager - Manages workpiece data for the contour editor.

This manager provides an abstraction layer between the editor and workpiece data.
It supports both:
1. Loading Workpiece objects (via WorkpieceAdapter)
2. Loading/exporting domain-agnostic ContourEditorData
"""
from ..handlers.workpiece_loader import load_workpiece
from ..adapters.workpiece_adapter import WorkpieceAdapter
from contour_editor import LayerConfigRegistry
from contour_editor.models.segment import Layer
from contour_editor.persistence.data.editor_data_model import ContourEditorData


class WorkpieceManager:
    def __init__(self, editor, default_settings: dict = None):
        self.editor = editor
        self.current_workpiece = None
        self.contours = None
        self._default_settings = default_settings or {}


    def load_workpiece(self, workpiece):
        """Load a workpiece and initialize its contours"""
        workpiece_result, new_contours_by_layer = load_workpiece(workpiece)
        self.current_workpiece = workpiece_result
        
        # Initialize the layers with the workpiece contours
        self.init_contour(new_contours_by_layer, close_contour=False)
        
        return workpiece_result

    def init_contour(self, contours_by_layer, close_contour=True):
        """
        Initialize contours. Supports both legacy format:
            { layer_name: [contour1, contour2, ...] }

        and new format (with settings):
            {
                layer_name: {
                    "contours": [...],
                    "settings": [...]
                }
            }
        """

        if contours_by_layer is None:
            return

        self.contours = contours_by_layer

        for layer_name, layer_data in contours_by_layer.items():
            # Handle both legacy and new input formats
            if isinstance(layer_data, dict) and "contours" in layer_data:
                contours = layer_data["contours"]
                settings_list = layer_data.get("settings", [None] * len(contours))
            else:
                contours = layer_data
                settings_list = [None] * len(contours)

            if not contours:
                continue

            # Iterate through contours and their associated settings
            for cnt, settings in zip(contours, settings_list):
                print(f"Passing contour with {len(cnt)} points to layer {layer_name}, settings: {settings}")

                bezier_segments = self.editor.manager.contour_to_bezier(cnt, close_contour=close_contour)

                for segment in bezier_segments:
                    segment.layer = Layer(layer_name, locked=False, visible=True)
                    # Merge: defaults first, then any non-empty per-segment overrides
                    effective = dict(self._default_settings)
                    if settings is not None and settings:
                        effective.update({k: v for k, v in dict(settings).items() if v is not None and v != ""})
                    segment.settings = effective
                    self.editor.manager.segments.append(segment)

        self.editor.pointsUpdated.emit()

    def apply_defaults_to_segments_without_settings(self) -> None:
        """Assign default settings to any segment that has none (newly drawn segments)."""
        for seg in self.editor.manager.get_segments():
            if not hasattr(seg, 'settings') or not seg.settings:
                seg.settings = dict(self._default_settings) if self._default_settings else {}

    def get_current_workpiece(self):
        """Get the currently loaded workpiece"""
        return self.current_workpiece

    def set_current_workpiece(self, workpiece):
        """Set the current workpiece"""
        self.current_workpiece = workpiece

    def get_contours(self):
        """Get the current contours data"""
        return self.contours

    def clear_workpiece(self):
        """Clear the current workpiece and all segments"""
        self.current_workpiece = None
        self.contours = None
        self.editor.manager.clear_all_segments()
        self.editor.update()

    def get_workpiece_statistics(self):
        """Get statistics about the current workpiece"""
        if not self.current_workpiece:
            return None

        segments = self.editor.manager.get_segments()
        
        stats = {
            "workpiece": self.current_workpiece,
            "total_segments": len(segments),
            "total_points": sum(len(segment.anchors) for segment in segments),
            "layers": {}
        }

        # Count segments and points per layer
        for segment in segments:
            if hasattr(segment, 'layer'):
                layer_name = segment.layer.name
                if layer_name not in stats["layers"]:
                    stats["layers"][layer_name] = {"segments": 0, "points": 0}
                
                stats["layers"][layer_name]["segments"] += 1
                stats["layers"][layer_name]["points"] += len(segment.anchors)

        return stats

    def validate_workpiece_data(self):
        """Validate the current workpiece data for consistency"""
        if not self.current_workpiece:
            return {"valid": False, "error": "No workpiece loaded"}

        segments = self.editor.manager.get_segments()
        errors = []

        # Check for segments without layers
        for i, segment in enumerate(segments):
            if not hasattr(segment, 'layer') or segment.layer is None:
                errors.append(f"Segment {i} has no layer assigned")

        # Check for empty segments
        for i, segment in enumerate(segments):
            if not hasattr(segment, 'anchors') or len(segment.anchors) < 2:
                errors.append(f"Segment {i} has insufficient anchor points")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "total_segments": len(segments)
        }

    # --- Domain-agnostic ContourEditorData methods ---

    def load_editor_data(self, editor_data: ContourEditorData, close_contour=True):
        """
        Load domain-agnostic ContourEditorData into the editor.

        This method allows loading contour data without any workpiece dependency.

        Args:
            editor_data: ContourEditorData instance
            close_contour: Whether to close contours when converting to Bezier

        Returns:
            ContourEditorData instance (passed through)
        """
        # Convert to legacy format and load
        contours_by_layer = editor_data.to_legacy_format()
        self.init_contour(contours_by_layer, close_contour=close_contour)

        # Clear workpiece reference since we're loading raw data
        self.current_workpiece = None

        return editor_data

    def export_editor_data(self) -> ContourEditorData:
        # Fill in defaults on any segment that was created programmatically
        # (e.g. zig-zag / fill generation) without going through init_contour.
        self.apply_defaults_to_segments_without_settings()

        editor_data = ContourEditorData()
        segments = self.editor.manager.get_segments()
        layers_dict = {}

        for segment in segments:
            # Segments drawn manually without an explicit layer assignment
            # default to the "Workpiece" layer (the workpiece boundary).
            if hasattr(segment, 'layer') and segment.layer:
                layer_name = segment.layer.name
            else:
                layer_name = LayerConfigRegistry.get_instance().get_config().name_for_role("workpiece")

            if layer_name not in layers_dict:
                locked = segment.layer.locked if (
                            hasattr(segment, 'layer') and segment.layer and hasattr(segment.layer, 'locked')) else False
                visible = segment.layer.visible if (
                            hasattr(segment, 'layer') and segment.layer and hasattr(segment.layer, 'visible')) else True
                layers_dict[layer_name] = Layer(name=layer_name, locked=locked, visible=visible)

            layers_dict[layer_name].add_segment(segment)

        for layer in layers_dict.values():
            editor_data.add_layer(layer)

        return editor_data

    def export_to_workpiece_data(self) -> dict:
        """
        Export the current editor state to a workpiece-compatible data structure.

        This uses the WorkpieceAdapter to convert the editor data to the
        format needed for creating or updating Workpiece objects.

        Returns:
            Dictionary with main_contour, main_settings, and spray_pattern data
        """
        # First export as ContourEditorData
        editor_data = self.export_editor_data()

        # Then use an adapter to convert to workpiece format
        return WorkpieceAdapter.to_workpiece_data(editor_data)

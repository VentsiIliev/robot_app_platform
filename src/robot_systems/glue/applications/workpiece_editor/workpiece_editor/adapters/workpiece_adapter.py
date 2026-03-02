from typing import Dict, Any, Optional
import numpy as np

from contour_editor.persistence.data.editor_data_model import ContourEditorData
from contour_editor.models.segment import Segment

from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config import SegmentSettingsProvider
from src.robot_systems.glue.workpieces.model.glue_workpiece_filed import GlueWorkpieceField


class WorkpieceAdapter:
    LAYER_WORKPIECE = "Workpiece"
    LAYER_CONTOUR = "Contour"
    LAYER_FILL = "Fill"

    @classmethod
    def _get_default_settings(cls) -> Dict[str, Any]:
        """Get default settings from SegmentSettingsProvider"""
        try:
            provider = SegmentSettingsProvider()
            return provider.get_default_values()
        except Exception as e:
            print(f"Warning: Could not load default settings from provider: {e}")
            return {}

    @classmethod
    def _ensure_complete_settings(cls, segment_settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Ensure segment settings are complete with default values for missing keys"""
        default_settings = cls._get_default_settings()

        if segment_settings is None:
            print("Segment has no settings, using defaults")
            return default_settings.copy()

        complete_settings = default_settings.copy()

        for key, value in segment_settings.items():
            if value is not None:
                complete_settings[key] = value

        none_keys = [k for k, v in complete_settings.items() if v is None]
        if none_keys:
            print(f"Warning: Found None values for keys: {none_keys}, replacing with defaults")
            for key in none_keys:
                if key in default_settings:
                    complete_settings[key] = default_settings[key]

        return complete_settings

    @classmethod
    def from_workpiece(cls, workpiece) -> ContourEditorData:
        main_contour = workpiece.get_main_contour()
        main_settings = workpiece.get_main_contour_settings()

        spray_contours = workpiece.get_spray_pattern_contours()
        spray_fills = workpiece.get_spray_pattern_fills()

        layer_data = {
            cls.LAYER_WORKPIECE: [{"contour": main_contour, "settings": main_settings}],
            cls.LAYER_CONTOUR: spray_contours,
            cls.LAYER_FILL: spray_fills,
        }

        normalized_data = cls._normalize_layer_data(layer_data)
        return ContourEditorData.from_legacy_format(normalized_data)

    @classmethod
    def to_workpiece_data(cls, editor_data: ContourEditorData) -> Dict[str, Any]:


        result = {}

        # Try to get main contour from WORKPIECE layer first
        workpiece_layer = editor_data.get_layer(cls.LAYER_WORKPIECE)
        main_segment = None

        if workpiece_layer and len(workpiece_layer.segments) > 0:
            main_segment = workpiece_layer.segments[0]
            print(f"[WorkpieceAdapter] Using WORKPIECE layer segment as main contour")
        else:
            # Fallback: use first CONTOUR segment as main contour
            contour_layer = editor_data.get_layer(cls.LAYER_CONTOUR)
            if contour_layer and len(contour_layer.segments) > 0:
                main_segment = contour_layer.segments[0]
                print(f"[WorkpieceAdapter] Using first CONTOUR segment as main contour (WORKPIECE layer empty)")

        if main_segment:
            result[GlueWorkpieceField.CONTOUR.value] = cls._segment_to_contour_array(main_segment)
            complete_settings = cls._ensure_complete_settings(
                main_segment.settings if hasattr(main_segment, 'settings') else None
            )
            result.update(complete_settings)
        else:
            print(f"[WorkpieceAdapter] No segments found, using empty contour")
            result[GlueWorkpieceField.CONTOUR.value] = np.zeros((0, 1, 2), dtype=np.float32)
            # Still need to provide default settings
            result.update(cls._ensure_complete_settings(None))

        spray_pattern = {
            "Contour": [],
            "Fill": []
        }

        contour_layer = editor_data.get_layer(cls.LAYER_CONTOUR)
        if contour_layer:
            for segment in contour_layer.segments:
                contour_array = cls._segment_to_contour_array(segment)
                if contour_array is not None and len(contour_array) > 0:
                    complete_settings = cls._ensure_complete_settings(
                        segment.settings if hasattr(segment, 'settings') else None
                    )
                    spray_pattern["Contour"].append({
                        "contour": contour_array,
                        "settings": complete_settings
                    })

        fill_layer = editor_data.get_layer(cls.LAYER_FILL)
        if fill_layer:
            for segment in fill_layer.segments:
                contour_array = cls._segment_to_contour_array(segment)
                if contour_array is not None and len(contour_array) > 0:
                    complete_settings = cls._ensure_complete_settings(
                        segment.settings if hasattr(segment, 'settings') else None
                    )
                    spray_pattern["Fill"].append({
                        "contour": contour_array,
                        "settings": complete_settings
                    })

        result[GlueWorkpieceField.SPRAY_PATTERN.value] = spray_pattern
        return result

    @staticmethod
    def _normalize_layer_data(layer_data: Dict[str, Any]) -> Dict[str, Dict[str, list]]:
        normalized = {}

        for layer_name, entries in layer_data.items():
            contours = []
            settings_list = []

            if not isinstance(entries, list):
                entries = [entries]

            for item in entries:
                if not isinstance(item, dict):
                    continue

                contour = np.array(item.get("contour", []), dtype=np.float32)

                if contour.ndim == 2 and contour.shape[1] == 2:
                    contour = contour.reshape(-1, 1, 2)
                elif contour.ndim == 3 and contour.shape[1] == 1:
                    pass
                else:
                    contour = contour.reshape(-1, 1, 2)

                contours.append(contour)
                settings_list.append(item.get("settings", {}))

            normalized[layer_name] = {
                "contours": contours,
                "settings": settings_list
            }

        return normalized

    @staticmethod
    def _segment_to_contour_array(segment: Segment) -> Optional[np.ndarray]:
        if len(segment.points) == 0:
            return None

        points = np.array(
            [[pt.x(), pt.y()] for pt in segment.points],
            dtype=np.float32
        ).reshape(-1, 1, 2)

        return points

    @classmethod
    def print_summary(cls, editor_data: ContourEditorData):
        print("\n=== WorkpieceAdapter Summary ===")

        workpiece_layer = editor_data.get_layer(cls.LAYER_WORKPIECE)
        if workpiece_layer:
            print(f"Main workpiece contour: {len(workpiece_layer.segments)} segment(s)")
        else:
            print("Main workpiece contour: N/A")

        contour_layer = editor_data.get_layer(cls.LAYER_CONTOUR)
        if contour_layer:
            print(f"Spray pattern contours: {len(contour_layer.segments)} segment(s)")
        else:
            print("Spray pattern contours: N/A")

        fill_layer = editor_data.get_layer(cls.LAYER_FILL)
        if fill_layer:
            print(f"Spray pattern fills: {len(fill_layer.segments)} segment(s)")
        else:
            print("Spray pattern fills: N/A")

        stats = editor_data.get_statistics()
        print(f"Total segments: {stats['total_segments']}")
        print(f"Total points: {stats['total_points']}")
        print("================================\n")

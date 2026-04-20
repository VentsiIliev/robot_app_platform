from typing import Dict, Any, Optional
import numpy as np

from contour_editor import LayerConfigRegistry
from contour_editor.persistence.data.editor_data_model import ContourEditorData
from PyQt6.QtCore import QPointF

from contour_editor.models.segment import Layer, Segment


class CaptureDataHandler:
    @classmethod
    def _layer_config(cls):
        return LayerConfigRegistry.get_instance().get_config()

    @classmethod
    def workpiece_layer_name(cls) -> str:
        return cls._layer_config().name_for_role("workpiece")

    @classmethod
    def contour_layer_name(cls) -> str:
        return cls._layer_config().name_for_role("contour")

    @classmethod
    def fill_layer_name(cls) -> str:
        return cls._layer_config().name_for_role("fill")

    @classmethod
    def handle_capture_data(
        cls,
        workpiece_manager,
        capture_data: Dict[str, Any],
        close_contour: bool = True
    ) -> Optional[ContourEditorData]:
        contours = capture_data.workpiece_contour
        if contours is None or (isinstance(contours, (list, np.ndarray)) and len(contours) == 0):
            return None

        editor_data = cls.from_capture_data(
            contours=contours,
            metadata={
                "height": capture_data.estimatedHeight,
                "source": "camera_capture"
            }
        )

        workpiece_manager.load_editor_data(editor_data, close_contour=close_contour)

        return editor_data

    @classmethod
    def from_capture_data(
        cls,
        contours: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ContourEditorData:
        editor_data = ContourEditorData()

        workpiece_layer = Layer(
            name=cls.workpiece_layer_name(),
            locked=False,
            visible=True
        )

        contour_array = cls._normalize_contour(contours)

        if contour_array is not None and len(contour_array) > 0:
            segment = Segment(layer=workpiece_layer)

            for pt in contour_array:
                if len(pt.shape) == 2 and pt.shape[0] == 1:
                    x, y = pt[0][0], pt[0][1]
                else:
                    x, y = pt[0], pt[1]
                segment.add_point(QPointF(float(x), float(y)))

            if metadata:
                segment.metadata = metadata

            workpiece_layer.add_segment(segment)

        editor_data.add_layer(workpiece_layer)

        cfg = cls._layer_config()
        if cfg.is_enabled("contour"):
            editor_data.add_layer(Layer(name=cls.contour_layer_name(), locked=False, visible=cfg.role("contour").visible))
        if cfg.is_enabled("fill"):
            editor_data.add_layer(Layer(name=cls.fill_layer_name(), locked=False, visible=cfg.role("fill").visible))

        return editor_data

    @staticmethod
    def _normalize_contour(contours: Any) -> Optional[np.ndarray]:
        if contours is None:
            return None

        if not isinstance(contours, np.ndarray):
            contours = np.array(contours, dtype=np.float32)

        if contours.ndim == 2 and contours.shape[1] == 2:
            return contours.reshape(-1, 1, 2)
        elif contours.ndim == 3 and contours.shape[1] == 1 and contours.shape[2] == 2:
            return contours
        elif contours.ndim == 3 and contours.shape[0] == 1:
            return contours.reshape(-1, 1, 2)
        else:
            try:
                return contours.reshape(-1, 1, 2)
            except ValueError:
                return None

    @classmethod
    def create_from_legacy_dict(
        cls,
        contours_by_layer: Dict[str, Any]
    ) -> ContourEditorData:
        return ContourEditorData.from_legacy_format(contours_by_layer)

    @classmethod
    def print_capture_summary(cls, editor_data: ContourEditorData):
        print("\n=== Capture Data Summary ===")
        stats = editor_data.get_statistics()

        for layer_name in cls._layer_config().enabled_layer_names():
            layer = editor_data.get_layer(layer_name)
            if layer:
                layer_stats = stats["layers"].get(layer_name, {})
                print(f"{layer_name}: {layer_stats.get('segments', 0)} segments, "
                      f"{layer_stats.get('points', 0)} points")

        print("============================\n")

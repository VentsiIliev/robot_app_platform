import numpy as np
from PyQt6.QtCore import QPointF
from shapely.geometry import Polygon, LineString

from ..persistence.utils.utils import shrink_contour_points, generate_spray_pattern


class ContourProcessingService:
    def __init__(self, manager):
        self.manager = manager

    def get_main_contour_points(self, layer_name=None):
        """
        Get contour points from the main layer.

        Args:
            layer_name: Optional layer name. If None, tries common layer names
                       ("Main", "Contour") or uses the first available layer.

        Returns:
            numpy array of contour points or None
        """
        # Try to find segments by layer name
        if layer_name:
            external_segments = [
                seg for seg in self.manager.get_segments()
                if hasattr(seg, 'layer') and seg.layer and seg.layer.name == layer_name
            ]
        else:
            common_names = (
                self.manager.get_main_contour_layer_names()
                if hasattr(self.manager, "get_main_contour_layer_names")
                else ["Main", "Contour"]
            )
            for common_name in common_names:
                external_segments = [
                    seg for seg in self.manager.get_segments()
                    if hasattr(seg, 'layer') and seg.layer and seg.layer.name == common_name
                ]
                if external_segments:
                    break

            # If still no segments, use the first layer with segments
            if not external_segments:
                all_segments = self.manager.get_segments()
                if all_segments:
                    external_segments = [all_segments[0]]

        if not external_segments:
            return None

        contour = external_segments[0]
        contour_points = np.array([(pt.x(), pt.y()) for pt in contour.points])

        if contour_points.size == 0 or contour_points.shape[0] < 3:
            return None

        return contour_points


    def shrink_contour(self, contour_points, shrink_amount):
        if contour_points is None or len(contour_points) < 3:
            return None

        new_contour_points = shrink_contour_points(contour_points, shrink_amount)

        if new_contour_points is None or len(new_contour_points) < 2:
            return None

        result = []
        for i in range(len(new_contour_points) - 1):
            p1 = new_contour_points[i]
            p2 = new_contour_points[i + 1]
            result.append([QPointF(float(p1[0]), float(p1[1])), QPointF(float(p2[0]), float(p2[1]))])

        return result

    def generate_spray_pattern(self, contour_points, spacing, shrink_offset=0):
        if contour_points is None or len(contour_points) < 3:
            return []

        if shrink_offset > 0:
            new_contour_points = shrink_contour_points(contour_points, shrink_offset)
            if new_contour_points is None or len(new_contour_points) < 2:
                return []
            contour_points = new_contour_points.astype(np.float32)
        else:
            contour_points = contour_points.astype(np.float32)

        zigzag_segments = generate_spray_pattern(contour_points, spacing)
        return zigzag_segments

    def create_segments_from_points(self, point_lists, layer_name):
        segments = []
        for points in point_lists:
            if points is None or len(points) < 2:
                continue

            qpoints = []
            for pt in points:
                if isinstance(pt, QPointF):
                    qpoints.append(pt)
                elif isinstance(pt, (list, tuple, np.ndarray)) and len(pt) >= 2:
                    qpoints.append(QPointF(float(pt[0]), float(pt[1])))

            if len(qpoints) >= 2:
                segment = self.manager.create_segment(qpoints, layer_name=layer_name)
                self.manager.segments.append(segment)
                segments.append(segment)
        return segments

    def create_fill_pattern(self, zigzag_segments, layer_name, contour_points):
        if zigzag_segments is None or len(zigzag_segments) == 0:
            return []

        contour_poly = Polygon(np.array(contour_points).squeeze())

        all_qpoints = []
        reverse = False
        prev_point = None

        for segment_coords in zigzag_segments:
            if segment_coords is None or len(segment_coords) < 2:
                continue

            pts = list(segment_coords)
            if reverse:
                pts = pts[::-1]

            if prev_point is not None:
                all_qpoints.append(QPointF(float(pts[0][0]), float(pts[0][1])))

            for pt in pts:
                all_qpoints.append(QPointF(float(pt[0]), float(pt[1])))

            prev_point = pts[-1]
            reverse = not reverse

        if all_qpoints and len(all_qpoints) >= 2:
            segment = self.manager.create_segment(all_qpoints, layer_name=layer_name)
            self.manager.segments.append(segment)
            return [segment]

        return []

    def create_contour_pattern(self, zigzag_segments, layer_name):
        if zigzag_segments is None or len(zigzag_segments) == 0:
            return []

        segments = []
        reverse = False

        for segment_coords in zigzag_segments:
            if segment_coords is None or len(segment_coords) < 2:
                continue

            pts = list(segment_coords)
            if reverse:
                pts = pts[::-1]

            qpoints = [QPointF(float(pt[0]), float(pt[1])) for pt in pts]

            if len(qpoints) >= 2:
                segment = self.manager.create_segment(qpoints, layer_name=layer_name)
                self.manager.segments.append(segment)
                segments.append(segment)

            reverse = not reverse

        return segments

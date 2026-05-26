from __future__ import annotations

import math
import copy

import numpy as np
from PyQt6.QtCore import QPointF

from .segment import Segment, Layer
from ..persistence.data.layer_config_registry import LayerConfigRegistry


class BezierSegmentManager:
    def __init__(self):
        self.layer_config = LayerConfigRegistry.get_instance().get_config()
        self.active_segment_index = 0
        self.undo_stack = []
        self.redo_stack = []
        self.external_layer = self._make_layer("workpiece")
        self.contour_layer = self._make_layer("contour")
        self.fill_layer = self._make_layer("fill")
        self.segments: list[Segment] = [Segment(layer=self._default_segment_layer())]

    def _make_layer(self, role_name: str) -> Layer:
        cfg = self.layer_config.role(role_name)
        return Layer(cfg.name, False, cfg.visible)

    def _role_layer_pairs(self):
        return (
            ("workpiece", self.external_layer),
            ("contour", self.contour_layer),
            ("fill", self.fill_layer),
        )

    def _layer_for_name(self, layer_name):
        for _, layer in self._role_layer_pairs():
            if layer.name == layer_name:
                return layer
        return None

    def _default_segment_layer(self):
        return self._layer_for_name(self.layer_config.default_segment_layer_name())

    def get_available_layer_names(self):
        return self.layer_config.enabled_layer_names()

    def get_pattern_layer_names(self):
        return self.layer_config.pattern_layer_names()

    def get_main_contour_layer_names(self):
        return self.layer_config.main_contour_layer_names()

    def is_fill_layer_name(self, layer_name):
        return self.layer_config.is_fill_layer_name(layer_name)

    def _is_layer_locked(self, layer_name):
        layer = self._layer_for_name(layer_name)
        return bool(layer and layer.locked)

    def undo(self):
        if not self.undo_stack:
            raise Exception("Nothing to undo.")
        self.redo_stack.append(copy.deepcopy(self.segments))
        self.segments = self.undo_stack.pop()

    def redo(self):
        if not self.redo_stack:
            raise Exception("Nothing to redo.")
        self.undo_stack.append(copy.deepcopy(self.segments))
        self.segments = self.redo_stack.pop()

    def save_state(self, max_stack_size=100):
        self.undo_stack.append(copy.deepcopy(self.segments))
        if len(self.undo_stack) > max_stack_size:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def set_active_segment(self, seg_index):
        if 0 <= seg_index < len(self.segments):
            segment = self.segments[seg_index]
            layer_name = getattr(segment, 'layer', None)

            if layer_name:
                if self._is_layer_locked(getattr(layer_name, "name", layer_name)):
                    return

            self.active_segment_index = seg_index

    def create_segment(self, points, layer_name=None):
        layer_name = layer_name or self.layer_config.default_segment_layer_name()
        layer = self._layer_for_name(layer_name)
        if layer is None:
            raise ValueError(f"Invalid layer name: {layer_name}")

        segment = Segment(layer=layer)
        for pt in points:
            segment.add_point(pt)
        return segment

    def start_new_segment(self, layer=None):
        layer = layer or self.layer_config.default_segment_layer_name()
        if len(self.segments) > 0:
            pass

        if layer:
            if self._is_layer_locked(layer):
                return None, False

        layer_obj = self._layer_for_name(layer)
        if layer_obj is None:
            raise ValueError(f"Invalid layer name: {layer}")

        new_segment = Segment(layer=layer_obj)
        self.segments.append(new_segment)
        layer_obj.add_segment(new_segment)
        self.active_segment_index = len(self.segments) - 1
        return new_segment, True

    def assign_segment_layer(self, seg_index, layer_name):
        segment = self.segments[seg_index]
        if segment.layer.locked:
            return

        if 0 <= seg_index < len(self.segments):
            layer = self._layer_for_name(layer_name)
            if layer is None:
                return
            segment.layer = layer

    def add_point(self, pos: QPointF):
        if 0 <= self.active_segment_index < len(self.segments):
            self.save_state()
            active_segment = self.segments[self.active_segment_index]

            if active_segment.layer is None:
                return

            if active_segment.layer.locked:
                return

            active_segment.add_point(pos)

    def get_segments(self):
        return self.segments

    def to_wp_data(self, samples_per_segment=5):
        path_points = {
            layer_name: [] for layer_name in self.get_available_layer_names()
        }

        def is_cp_effective(p0, cp, p1, threshold=1.0):
            dx, dy = p1.x() - p0.x(), p1.y() - p0.y()
            if dx == dy == 0:
                return False
            distance = abs(dy * cp.x() - dx * cp.y() + p1.x() * p0.y() - p1.y() * p0.x()) / ((dx ** 2 + dy ** 2) ** 0.5)
            return distance > threshold

        def to_opencv_contour(path):
            if not path or not all(isinstance(pt, (list, tuple)) and len(pt) == 2 for pt in path):
                return None
            return np.array(path, dtype=np.float32).reshape(-1, 1, 2)

        for segment in self.segments:
            raw_path = []
            points = segment.points
            controls = segment.controls

            if points:
                raw_path.append([points[0].x(), points[0].y()])

            for i in range(1, len(points)):
                p0, p1 = points[i - 1], points[i]
                if i - 1 < len(controls) and controls[i - 1] is not None and is_cp_effective(p0, controls[i - 1], p1):
                    for t in [j / samples_per_segment for j in range(1, samples_per_segment + 1)]:
                        x = (1 - t) ** 2 * p0.x() + 2 * (1 - t) * t * controls[i - 1].x() + t ** 2 * p1.x()
                        y = (1 - t) ** 2 * p0.y() + 2 * (1 - t) * t * controls[i - 1].y() + t ** 2 * p1.y()
                        raw_path.append([x, y])
                else:
                    raw_path.append([p1.x(), p1.y()])

            contour = to_opencv_contour(raw_path)
            if contour is not None:
                path_points[segment.layer.name].append({
                    "contour": contour,
                    "settings": dict(segment.settings)
                })

        for layer_name in self.get_available_layer_names():
            if not path_points[layer_name]:
                path_points[layer_name].append({
                    "contour": np.empty((0, 1, 2), dtype=np.float32),
                    "settings": {}
                })

        return path_points

    def get_active_segment(self):
        if self.active_segment_index is not None and 0 <= self.active_segment_index < len(self.segments):
            return self.segments[self.active_segment_index]
        return None

    def disconnect_line_segment(self, seg_index, line_index):
        self.save_state()

        if seg_index < 0 or seg_index >= len(self.segments):
            return False

        segment = self.segments[seg_index]

        if segment.layer.locked:
            return False

        if line_index < 0 or line_index >= len(segment.points) - 1:
            return False

        if len(segment.points) <= 2:
            return False

        segments_to_insert = []
        insertion_index = seg_index

        if line_index > 0:
            before_segment = Segment(layer=segment.layer, settings=segment.settings)

            for i in range(line_index + 1):
                before_segment.points.append(segment.points[i])

            for i in range(line_index):
                if i < len(segment.controls):
                    before_segment.controls.append(segment.controls[i])
                else:
                    before_segment.controls.append(None)

            segments_to_insert.append(before_segment)

        disconnected_segment = Segment(layer=segment.layer, settings=segment.settings)

        disconnected_segment.points.append(segment.points[line_index])
        disconnected_segment.points.append(segment.points[line_index + 1])

        if line_index < len(segment.controls):
            disconnected_segment.controls.append(segment.controls[line_index])
        else:
            disconnected_segment.controls.append(None)

        segments_to_insert.append(disconnected_segment)

        if line_index + 2 < len(segment.points):
            after_segment = Segment(layer=segment.layer, settings=segment.settings)

            for i in range(line_index + 1, len(segment.points)):
                after_segment.points.append(segment.points[i])

            for i in range(line_index + 1, len(segment.controls)):
                after_segment.controls.append(segment.controls[i])

            while len(after_segment.controls) < len(after_segment.points) - 1:
                after_segment.controls.append(None)

            segments_to_insert.append(after_segment)

        del self.segments[seg_index]

        for i, new_segment in enumerate(segments_to_insert):
            self.segments.insert(seg_index + i, new_segment)

        if self.active_segment_index == seg_index:
            self.active_segment_index = seg_index + (1 if line_index > 0 else 0)
        elif self.active_segment_index > seg_index:
            self.active_segment_index += len(segments_to_insert) - 1

        return True

    def get_robot_path(self, samples_per_segment=5):
        path_points = []

        def is_cp_effective(p0, cp, p1, threshold=1.0):
            dx, dy = p1.x() - p0.x(), p1.y() - p0.y()
            if dx == dy == 0:
                return False
            distance = abs(dy * cp.x() - dx * cp.y() + p1.x() * p0.y() - p1.y() * p0.x()) / ((dx ** 2 + dy ** 2) ** 0.5)
            return distance > threshold

        for segment in self.segments:
            points = segment.points
            controls = segment.controls
            for i in range(1, len(points)):
                p0, p1 = points[i - 1], points[i]
                if i - 1 < len(controls) and controls[i - 1] is not None and is_cp_effective(p0, controls[i - 1], p1):
                    for t in [j / samples_per_segment for j in range(samples_per_segment + 1)]:
                        x = (1 - t) ** 2 * p0.x() + 2 * (1 - t) * t * controls[i - 1].x() + t ** 2 * p1.x()
                        y = (1 - t) ** 2 * p0.y() + 2 * (1 - t) * t * controls[i - 1].y() + t ** 2 * p1.y()
                        path_points.append(QPointF(x, y))
                else:
                    path_points.extend([p0, p1])

        return path_points

    def delete_segment(self, seg_index):
        if 0 <= seg_index < len(self.segments):
            segment = self.segments[seg_index]

            if segment.layer.locked:
                return

            del self.segments[seg_index]
            if not self.segments:
                self.active_segment_index = -1
            elif self.active_segment_index == seg_index:
                self.active_segment_index = len(self.segments) - 1
            elif self.active_segment_index > seg_index:
                self.active_segment_index -= 1

    def set_segment_visibility(self, seg_index, visible):
        if 0 <= seg_index < len(self.segments):
            self.segments[seg_index].visible = visible

    def is_segment_visible(self, seg_index):
        if 0 <= seg_index < len(self.segments):
            return self.segments[seg_index].visible
        return False

    def has_control_points(self, seg_index):
        if 0 <= seg_index < len(self.segments):
            return len(self.segments[seg_index].controls) > 0
        return False

    def find_all_drag_targets(self, pos, threshold=5.0):
        targets = []
        for seg_idx, segment in enumerate(self.segments):
            for idx, pt in enumerate(segment.points):
                dx = pt.x() - pos.x()
                dy = pt.y() - pos.y()
                distance = math.hypot(dx, dy)
                if distance <= threshold:
                    targets.append(("anchor", seg_idx, idx))
            for idx, ctrl in enumerate(segment.controls):
                if ctrl is None:
                    continue
                dx = ctrl.x() - pos.x()
                dy = ctrl.y() - pos.y()
                distance = math.hypot(dx, dy)
                if distance <= threshold:
                    targets.append(("control", seg_idx, idx))
        return targets

    def find_drag_target(self, pos, threshold=10):
        for seg_index, seg in enumerate(self.segments):

            if seg_index != self.active_segment_index:
                continue

            if seg.layer.locked:
                continue

            for i, pt in enumerate(seg.controls):
                if pt is None:
                    continue
                if (pt - pos).manhattanLength() < threshold:
                    return 'control', seg_index, i

            for i, pt in enumerate(seg.points):
                if (pt - pos).manhattanLength() < threshold:
                    return 'anchor', seg_index, i

        return None

    def reset_control_point(self, seg_index, ctrl_idx):
        self.save_state()
        segment = self.segments[seg_index]

        if 0 <= ctrl_idx < len(segment.controls) and ctrl_idx < len(segment.points):
            segment.controls[ctrl_idx] = QPointF(segment.points[ctrl_idx])

    def move_point(self, role, seg_index, idx, new_pos, suppress_save=False):
        if not suppress_save:
            self.save_state()

        segment = self.segments[seg_index]

        if segment.layer.locked:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            parent = QApplication.activeWindow()
            QMessageBox.warning(parent, "Layer Locked",
                                f"Cannot move point: Layer '{segment.layer.name}' is locked.")
            return

        points = segment.points
        controls = segment.controls

        if role == 'anchor':
            old_pos = points[idx]
            delta = new_pos - old_pos
            points[idx] = new_pos

            if idx > 0 and idx - 1 < len(controls):
                p0, ctrl = points[idx - 1], controls[idx - 1]
                if self.is_on_line(p0, ctrl, old_pos):
                    controls[idx - 1] = (p0 + new_pos) / 2

            if idx < len(points) - 1 and idx < len(controls):
                p1, ctrl = points[idx + 1], controls[idx]
                if self.is_on_line(old_pos, ctrl, p1):
                    controls[idx] = (new_pos + p1) / 2

        elif role == 'control':
            controls[idx] = new_pos

    def remove_control_point_at(self, pos, threshold=10):
        self.save_state()
        for seg in self.segments:

            if seg.layer is None:
                return False

            if seg.layer.locked:
                return False

            for i, pt in enumerate(seg.controls):
                if pt is None:
                    continue
                if (pt - pos).manhattanLength() < threshold:
                    seg.remove_point(i)
                    if i + 1 < len(seg.points):
                        del seg.points[i + 1]
                    return True
        return False

    def remove_point(self, role, seg_index, idx):
        self.save_state()
        segment = self.segments[seg_index]

        layer_name = getattr(segment, 'layer', None)
        if layer_name:
            if self._is_layer_locked(getattr(layer_name, "name", layer_name)):
                return

        if role == 'anchor':
            del segment.points[idx]
        elif role == 'control':
            del segment.controls[idx]
        else:
            raise ValueError("Role must be 'anchor' or 'control'")

    @staticmethod
    def is_on_line(p0, cp, p1, threshold=1.0):
        if cp is None:
            return False

        dx = p1.x() - p0.x()
        dy = p1.y() - p0.y()

        if dx == 0 and dy == 0:
            return False

        v1x = cp.x() - p0.x()
        v1y = cp.y() - p0.y()

        v2x = dx
        v2y = dy

        dot = v1x * v2x + v1y * v2y
        len_sq = v2x * v2x + v2y * v2y

        if dot < 0 or dot > len_sq:
            return False

        distance = abs(dy * cp.x() - dx * cp.y() + p1.x() * p0.y() - p1.y() * p0.x()) / ((dx ** 2 + dy ** 2) ** 0.5)

        return distance < threshold

    def add_control_point(self, segment_index, pos):
        self.save_state()

        segment = self.segments[segment_index]

        if segment.layer.locked:
            return False

        segment_info = self.find_segment_at(pos)
        if not segment_info:
            return False

        seg_index, line_index = segment_info
        p0 = segment.points[line_index]
        p1 = segment.points[line_index + 1]

        midpoint = (p0 + p1) * 0.5
        if line_index < len(segment.controls):
            segment.controls[line_index] = midpoint
        else:
            while len(segment.controls) < line_index:
                segment.controls.append(None)
            segment.controls.append(midpoint)

        return True

    def insert_anchor_point(self, segment_index, pos):
        self.save_state()

        segment = self.segments[segment_index]

        if segment.layer.locked:
            return False

        segment_info = self.find_segment_at(pos)
        if not segment_info:
            return False

        seg_index, line_index = segment_info
        if seg_index != segment_index:
            return False

        p0 = segment.points[line_index]
        p1 = segment.points[line_index + 1]

        dx = p1.x() - p0.x()
        dy = p1.y() - p0.y()
        segment_length_squared = dx * dx + dy * dy

        if segment_length_squared == 0:
            return False

        px = pos.x() - p0.x()
        py = pos.y() - p0.y()

        t = (px * dx + py * dy) / segment_length_squared
        t = max(0.0, min(1.0, t))

        insert_x = p0.x() + t * dx
        insert_y = p0.y() + t * dy
        insert_point = QPointF(insert_x, insert_y)

        segment.points.insert(line_index + 1, insert_point)

        if line_index < len(segment.controls):
            old_control = segment.controls[line_index]

            if old_control is not None:
                ctrl1 = QPointF(
                    p0.x() + t * (old_control.x() - p0.x()),
                    p0.y() + t * (old_control.y() - p0.y())
                )

                ctrl2 = QPointF(
                    insert_point.x() + (1 - t) * (old_control.x() - p0.x()),
                    insert_point.y() + (1 - t) * (old_control.y() - p0.y())
                )

                segment.controls[line_index] = ctrl1
                segment.controls.insert(line_index + 1, ctrl2)
            else:
                segment.controls.insert(line_index + 1, None)
        else:
            segment.controls.insert(line_index + 1, None)

        return True

    def find_segment_at(self, pos, threshold=10):
        for seg_index, segment in enumerate(self.segments):
            points = segment.points
            for i in range(1, len(points)):
                p0 = points[i - 1]
                p1 = points[i]

                if self.is_on_segment(p0, pos, p1, threshold):
                    return seg_index, i - 1

        return None

    @staticmethod
    def is_on_segment(p0, test_pt, p1, threshold=5.0):
        if test_pt is None:
            return False

        dx = p1.x() - p0.x()
        dy = p1.y() - p0.y()
        segment_length_squared = dx * dx + dy * dy
        if segment_length_squared == 0:
            return False

        px = test_pt.x() - p0.x()
        py = test_pt.y() - p0.y()

        t = (px * dx + py * dy) / segment_length_squared

        if t < 0.0 or t > 1.0:
            return False

        proj_x = p0.x() + t * dx
        proj_y = p0.y() + t * dy

        dist = ((test_pt.x() - proj_x) ** 2 + (test_pt.y() - proj_y) ** 2) ** 0.5

        return dist <= threshold

    def set_layer_locked(self, layer_name, locked):
        layer = self._layer_for_name(layer_name)
        if layer is not None:
            layer.locked = locked

        self._fix_segment_layer_references()

    def _fix_segment_layer_references(self):
        for i, segment in enumerate(self.segments):
            if not segment.layer:
                continue
            canonical_layer = self._layer_for_name(segment.layer.name)
            if canonical_layer is not None and segment.layer is not canonical_layer:
                segment.layer = canonical_layer

    def isLayerLocked(self, layer_name):
        layer = self._layer_for_name(layer_name)
        if layer is not None:
            return layer.locked
        return None

    def get_significant_points(self, points, num_points):
        if len(points) <= num_points:
            return points.copy()

        curvatures = []
        for i in range(1, len(points) - 1):
            p0, p1, p2 = points[i - 1], points[i], points[i + 1]
            v1 = np.array([p1.x() - p0.x(), p1.y() - p0.y()])
            v2 = np.array([p2.x() - p1.x(), p2.y() - p1.y()])
            if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
                angle = 0.0
            else:
                cos_theta = np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1)
                angle = np.arccos(cos_theta)
            curvatures.append((i, angle))

        selected_indices = {0, len(points) - 1}

        curvatures.sort(key=lambda x: x[1], reverse=True)
        for idx, _ in curvatures:
            if len(selected_indices) >= num_points:
                break
            selected_indices.add(idx)

        return [points[i] for i in sorted(selected_indices)]

    def contour_to_bezier(self, contour, num_points=None, control_point_ratio=0.5, close_contour=True, settings=None,
                          straight_threshold=0.5):
        if len(contour) < 2:
            return []

        if close_contour:
            start_pt = contour[0][0]
            end_pt = contour[-1][0]
            if not np.allclose(start_pt, end_pt):
                contour = np.vstack([contour, [contour[0]]])

        points = [QPointF(pt[0][0], pt[0][1]) for pt in contour]

        if num_points is not None and num_points < len(points):
            points = self.get_significant_points(points, num_points)

        self.external_layer.locked = False
        segment = Segment(self.external_layer, settings)
        self.external_layer.locked = True

        for pt in points:
            segment.add_point(pt)

        for i in range(len(segment.points) - 1):
            p0 = segment.points[i]
            p1 = segment.points[i + 1]

            control_x = (1 - control_point_ratio) * p0.x() + control_point_ratio * p1.x()
            control_y = (1 - control_point_ratio) * p0.y() + control_point_ratio * p1.y()
            control_pt = QPointF(control_x, control_y)

            dx = p1.x() - p0.x()
            dy = p1.y() - p0.y()

            denom = math.hypot(dx, dy)
            if denom == 0:
                dist = 0.0
            else:
                dist = abs(dy * control_pt.x() - dx * control_pt.y() + p1.x() * p0.y() - p1.y() * p0.x()) / denom

            if dist > straight_threshold:
                segment.add_control_point(i, control_pt)
            else:
                segment.add_control_point(i, None)

        return [segment]

    def clear_all_segments(self):
        self.segments.clear()
        self.active_segment_index = -1

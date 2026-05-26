from PyQt6.QtCore import QPointF
from typing import Optional


class Segment:
    def __init__(self, layer=None, settings=None):
        self.points: list[QPointF] = []
        self.controls: list[QPointF | None] = []
        self.visible = True
        self.layer = layer
        if settings is None:
            self.settings = {}
        else:
            self.settings = settings

    def set_settings(self, settings: dict):
        self.settings = settings

    def add_point(self, point: QPointF):
        self.points.append(point)
        if len(self.points) > 1:
            self.controls.append(None)

    def remove_point(self, index: int):
        if 0 <= index < len(self.points):
            del self.points[index]
            if index < len(self.controls):
                del self.controls[index]

    def add_control_point(self, index: int, point: QPointF):
        if 0 <= index < len(self.controls):
            self.controls[index] = point
        else:
            self.controls.append(point)

    def set_layer(self, layer):
        self.layer = layer

    def get_external_layer(self):
        return self.layer if self.layer else None

    def get_contour_layer(self):
        return self.layer if self.layer else None

    def get_fill_layer(self):
        return self.layer if self.layer else None

    def __str__(self):
        return f"Segment(points={len(self.points)}, controls={len(self.controls)}, visible={self.visible}, layer={self.layer.name if self.layer else None})"


class Layer:
    def __init__(self, name, locked=False, visible=True):
        self.name = name
        self.locked = locked
        self.visible = visible
        self.segments: list[Segment] = []

    def add_segment(self, segment: Segment):
        self.segments.append(segment)

    def remove_segment(self, index: int):
        if 0 <= index < len(self.segments):
            del self.segments[index]

    def __str__(self):
        return f"Layer(name={self.name}, locked={self.locked}, visible={self.visible}, segments={len(self.segments)})"


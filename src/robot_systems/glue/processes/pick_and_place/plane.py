from src.robot_systems.glue.processes.pick_and_place.config import PlaneConfig


class Plane:
    def __init__(self, config: PlaneConfig):
        self.xMin = config.x_min
        self.xMax = config.x_max
        self.yMin = config.y_min
        self.yMax = config.y_max
        self.spacing       = config.spacing
        self.xOffset       = 0.0
        self.yOffset       = 0.0
        self.tallestContour = 0.0
        self.rowCount      = 0
        self.isFull        = False
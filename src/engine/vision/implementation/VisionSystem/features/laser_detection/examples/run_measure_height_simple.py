import logging
import cv2

from modules.VisionSystem.laser_detection.height_measuring import HeightMeasuringService
from modules.VisionSystem.laser_detection.laser_detection_service import LaserDetectionService
from modules.VisionSystem.laser_detection.laser_detector import LaserDetector, LaserDetectionConfig
from modules.VisionSystem.laser_detection.utils import init_vision_service, init_robot_service
from modules.shared.tools.Laser import Laser

_logger = logging.getLogger(__name__)
WINDOW_NAME = "Laser Height Measurement - Live View"
if __name__ == "__main__":

    vs = init_vision_service()
    rs = init_robot_service()
    ld = LaserDetector(LaserDetectionConfig())
    lds = LaserDetectionService(detector=ld, laser=Laser(), vision_service=vs)
    hms = HeightMeasuringService(laser_detection_service=lds, robot_service=rs)
    chessboard_width = vs.camera_settings.get_chessboard_width()
    chessboard_height = vs.camera_settings.get_chessboard_height()
    square_size_mm = vs.camera_settings.get_square_size_mm()

    # Create visualization window
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 1280, 720)


    # Create visualization window
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 1280, 720)


    while True:
        image = vs.latest_frame
        if image is None:
            _logger.info(f"Waiting for camera frame...")


            continue

        height_mm, pixel_data = hms.measure_at()
        _logger.info(f"Height Measurement: {height_mm:.2f} mm")

        out = image.copy()
        cv2.putText(
            out,
            f"Measured Height: {height_mm:.2f} mm",
            (30, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 255, 0),
            2,
        )
        cv2.imshow(WINDOW_NAME, out)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
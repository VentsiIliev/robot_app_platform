import logging
import time
import cv2

from modules.VisionSystem.laser_detection.laser_detection_service import LaserDetectionService
from modules.VisionSystem.laser_detection.laser_detector import LaserDetector, LaserDetectionConfig
from modules.VisionSystem.laser_detection.utils import init_vision_service, init_robot_service
from modules.shared.tools.Laser import Laser

_logger = logging.getLogger(__name__)

if __name__ == "__main__":
    def draw_crosshair_full_image(frame, color=(0, 255, 0), thickness=2):
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.line(frame, (0, cy), (w - 1, cy), color, thickness)
        cv2.line(frame, (cx, 0), (cx, h - 1), color, thickness)

    # Trackbar callback (does nothing, value read later)
    def on_trackbar(val):
        pass

    def main():
        vs = init_vision_service()
        vs.camera_settings.set_brightness_auto(False)
        rs = init_robot_service()
        ld = LaserDetector(LaserDetectionConfig())
        lds = LaserDetectionService(detector=ld, laser=Laser(), vision_service=vs)

        # Create window and trackbar for delay_ms
        # cv2.namedWindow("Controls", cv2.WINDOW_NORMAL)
        # cv2.resizeWindow("Controls", 300, 50)
        # cv2.createTrackbar("Delay ms", "Controls", 200, 5000, on_trackbar)  # default 1000ms, max 5000ms

        while True:
            frame = vs.latest_frame
            if frame is None:
                _logger.info(f"Waiting for camera frame...")

                time.sleep(0.1)
                continue

            mask, bright, closest = lds.detect()

            if lds.last_on_frame is None:
                _logger.info(f"Waiting for laser ON frame...")

                time.sleep(0.1)
                continue

            out = lds.last_on_frame.copy()
            draw_crosshair_full_image(out)

            if bright is not None:
                cv2.circle(out, bright, 5, (0, 255, 255), 2)

            if closest is not None:
                _logger.info(f"Drawing closest point at ({closest[0]:.2f}, {closest[1]:.2f})")

                x = int(round(closest[0]))
                y = int(round(closest[1]))
                cv2.circle(out, (x, y), 6, (255, 255, 0), 2)
                # put text with coordinates
                cv2.putText(
                    out,
                    f"({closest[0]:.1f}, {closest[1]:.1f})",
                    (x + 10, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 0),
                    1,
                )
                _logger.info(f"closest point: ({closest[0]:.2f}, {closest[1]:.2f}) at robot height Z=343.112mm")


            cv2.imshow("Laser Line Overlay", out)

            if lds.last_on_frame is not None:
                cv2.imshow("Laser ON Frame", lds.last_on_frame)
            if lds.last_off_frame is not None:
                cv2.imshow("Laser OFF Frame", lds.last_off_frame)

            if mask is not None:
                cv2.imshow("Laser Detection Mask", mask)

            cv2.imshow("Camera Frame", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cv2.destroyAllWindows()

    main()

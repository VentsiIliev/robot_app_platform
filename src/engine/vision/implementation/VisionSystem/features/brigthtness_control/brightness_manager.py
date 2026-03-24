import logging
import numpy as np

from src.engine.vision.implementation.plvision.PLVision.PID.BrightnessController import BrightnessController

_logger = logging.getLogger(__name__)


class BrightnessManager:
    def __init__(self, vision_system):
        self.brightnessAdjustment = 0
        self.adjustment = None
        self.vision_system = vision_system
        self.brightnessController = BrightnessController(
            Kp=self.vision_system.camera_settings.get_brightness_kp(),
            Ki=self.vision_system.camera_settings.get_brightness_ki(),
            Kd=self.vision_system.camera_settings.get_brightness_kd(),
            setPoint=self.vision_system.camera_settings.get_target_brightness()
        )

    def auto_brightness_control_off(self):
        self.vision_system.camera_settings.set_brightness_auto(False)

    def auto_brightness_control_on(self):
        self.vision_system.camera_settings.set_brightness_auto(True)

    def on_brighteness_toggle(self, mode):
        if mode == "start":
            self.vision_system.camera_settings.set_brightness_auto(True)
        elif mode == "stop":
            self.vision_system.camera_settings.set_brightness_auto(False)
        else:
            _logger.info(f"on_brightness_toggle Invalid mode {mode}")


    def get_area_by_threshold(self):
        active_area = self.vision_system.threshold_by_area
        if not active_area:
            return None
        return self.vision_system._get_area_points_by_region(active_area)

    def adjust_brightness(self):
        # Get area points from camera settings, with fallback to hardcoded values
        try:
            area_points = self.vision_system.camera_settings.get_brightness_area_points()
            if area_points and len(area_points) == 4:
                # Convert from [x, y] list format to tuple format
                area_p1 = tuple(area_points[0])
                area_p2 = tuple(area_points[1])
                area_p3 = tuple(area_points[2])
                area_p4 = tuple(area_points[3])
            else:
                # Fallback to hardcoded values if settings not available
                area_p1, area_p2, area_p3, area_p4 = (940, 612), (1004, 614), (1004, 662), (940, 660)
        except Exception as e:
            # Fallback to hardcoded values on any error
            area_p1, area_p2, area_p3, area_p4 = (940, 612), (1004, 614), (1004, 662), (940, 660)
            _logger.error(f"Error loading brightness area from settings, using fallback: {e}")


        area = np.array([area_p1, area_p2, area_p3, area_p4], dtype=np.float32)

        # Apply current cumulative adjustment first
        adjusted_frame = self.brightnessController.adjustBrightness(self.vision_system.image, self.brightnessAdjustment)

        # Measure brightness of the adjusted frame (feedback loop)
        current_brightness = self.brightnessController.calculateBrightness(adjusted_frame, area)

        # Calculate the error based on what we actually achieved
        error = self.brightnessController.target - current_brightness

        # Compute correction to add to cumulative adjustment
        # Use proportional control with damping for stability
        if abs(error) > 10:
            # Larger errors - use 60% for faster convergence but stability
            correction = error * 0.6
        elif abs(error) > 2:
            # Medium errors - use 40% for smooth approach
            correction = error * 0.4
        else:
            # Small errors - use 100% to eliminate steady-state error
            correction = error

        # Update cumulative adjustment
        self.brightnessAdjustment += correction

        # Clamp total adjustment to valid range
        self.brightnessAdjustment = np.clip(self.brightnessAdjustment, -255, 255)

        # Apply the updated cumulative adjustment
        final_frame = self.brightnessController.adjustBrightness(self.vision_system.image, self.brightnessAdjustment)

        # Measure final result for logging
        final_brightness = self.brightnessController.calculateBrightness(final_frame, area)

        # Log when error is significant
        final_error = abs(self.brightnessController.target - final_brightness)
        # if final_error > 2:  # Lower threshold to see convergence
        #     print(f"[BrightnessManager] Current: {current_brightness:.1f}, Error: {error:.1f}, Correction: {correction:.2f}, Total Adj: {self.brightnessAdjustment:.1f}, Final: {final_brightness:.1f}")

        self.vision_system.image = final_frame

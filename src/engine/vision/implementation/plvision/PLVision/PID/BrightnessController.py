"""
* File: PIDController.y_pixels
* Author: IlV
* Comments:
* Revision history:
* Date       Author      Description
* -----------------------------------------------------------------
** 100624     IlV         Initial release
* -----------------------------------------------------------------
*
"""

import cv2
import numpy as np

from ..PID.PIDController import PIDController


class BrightnessController(PIDController):
    def __init__(self, Kp, Ki, Kd, setPoint):
        super().__init__(Kp, Ki, Kd, setPoint)
        self.output_min = -255  # Full range to handle any lighting condition
        self.output_max = 255
        self._roi_cache_key = None
        self._roi_cache_mask = None
        self._roi_cache_bounds = None

    def calculateBrightness(self, frame, roi_points=None):
        """
        Calculate the brightness of a frame, optionally within a specific region of interest.

        Args:
            frame (np.array): The frame to calculate the brightness of.
            roi_points (np.array, optional): Points defining the region of interest. 
                                           If None, calculates brightness of entire frame.

        Returns:
            float: The brightness of the frame or region.
        """
        # If no ROI specified, calculate brightness of entire frame (backward compatibility)
        if roi_points is None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return cv2.mean(gray)[0]

        x, y, w, h, mask = self._get_or_build_roi_cache(frame, roi_points)
        region = frame[y:y + h, x:x + w]
        if region.size == 0:
            return 0.0

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        region_brightness = cv2.mean(gray, mask=mask)[0]
        # print(f"[BrightnessController] Calculated region brightness: {region_brightness}")
        return region_brightness

    def _get_or_build_roi_cache(self, frame, roi_points):
        frame_h, frame_w = frame.shape[:2]
        if len(roi_points.shape) == 3:
            roi_points_xy = roi_points.reshape(-1, 2)
        else:
            roi_points_xy = roi_points.reshape(-1, 2)

        roi_points_int = roi_points_xy.astype(np.int32)
        key = (
            frame_w,
            frame_h,
            tuple((int(x), int(y)) for x, y in roi_points_int.tolist()),
        )
        if (
            key == self._roi_cache_key
            and self._roi_cache_mask is not None
            and self._roi_cache_bounds is not None
        ):
            x, y, w, h = self._roi_cache_bounds
            return x, y, w, h, self._roi_cache_mask

        polygon = roi_points_int.reshape((-1, 1, 2))
        x, y, w, h = cv2.boundingRect(polygon)
        local_polygon = polygon.copy()
        local_polygon[:, 0, 0] -= x
        local_polygon[:, 0, 1] -= y

        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [local_polygon], 255)

        self._roi_cache_key = key
        self._roi_cache_mask = mask
        self._roi_cache_bounds = (x, y, w, h)
        return x, y, w, h, mask

    def compute_with_antiwindup(self, currentValue):
        """
        Compute PID output with anti-windup (back-calculation method).
        Only accumulates integral when output is not saturated.

        Args:
            currentValue (float): The current value to be controlled.

        Returns:
            float: The clamped output of the PID controller.
        """
        # Calculate the error
        error = self.target - currentValue

        # Calculate the proportional term
        p_term = self.Kp * error

        # Calculate the derivative term
        derivative = error - self.previousError
        d_term = self.Kd * derivative

        # Calculate the integral term
        i_term = self.Ki * self.integral

        # Compute unclamped output
        output = p_term + i_term + d_term

        # Clamp the output
        clamped_output = np.clip(output, self.output_min, self.output_max)

        # Anti-windup: only integrate if not saturated
        # or if integration would reduce the error
        if (output == clamped_output) or (np.sign(error) != np.sign(self.integral)):
            self.integral += error
        # else: don't integrate when saturated to prevent windup

        # Update the previous error
        self.previousError = error

        return clamped_output

    def adjustBrightness(self, frame, adjustment):
        """
        Adjust the brightness of a frame, optionally within a specific region of interest.

        Args:
            frame (np.array): The frame to adjust the brightness of.
            adjustment (float): The amount to adjust the brightness by.

        Returns:
            np.array: The frame with adjusted brightness.
        """
        # Clip the adjustment to full pixel value range
        adjustment = np.clip(adjustment, -255, 255)

        # print(f"[BrightnessController] Applying global brightness adjustment: {adjustment}")
        return cv2.convertScaleAbs(frame, alpha=1, beta=adjustment)

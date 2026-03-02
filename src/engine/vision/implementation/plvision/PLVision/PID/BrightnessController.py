"""
* File: PIDController.py
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
        # Convert the frame to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # If no ROI specified, calculate brightness of entire frame (backward compatibility)
        if roi_points is None:
            return cv2.mean(gray)[0]
        
        # Create mask for the region of interest
        mask = np.zeros(gray.shape[:2], dtype=np.uint8)
        
        # Convert points to proper format for fillPoly
        if len(roi_points.shape) == 3:
            # Already in (N, 1, 2) format
            roi_points_int = roi_points.astype(np.int32)
        else:
            # Convert (N, 2) to (N, 1, 2) format
            roi_points_int = roi_points.astype(np.int32).reshape((-1, 1, 2))
        
        # Fill the polygon area in the mask
        cv2.fillPoly(mask, [roi_points_int], 255)
        
        # Calculate mean brightness only within the masked region
        region_brightness = cv2.mean(gray, mask=mask)[0]
        # print(f"[BrightnessController] Calculated region brightness: {region_brightness}")
        return region_brightness

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

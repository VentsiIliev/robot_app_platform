"""
Plugin-internal JSON mapper.

Translates between the nested camera_settings.json format and
CameraSettingsData (plugin DTO).

No vision system imports — this file belongs entirely to the plugin layer.
Cross-layer mapping (CameraSettings ↔ CameraSettingsData) lives in
src/adapter/mapper.py (VisionSystemSettingsMapper).
"""
from __future__ import annotations

from typing import List, Tuple

from src.plugin.camera_settings.camera_settings_data import CameraSettingsData


class CameraSettingsMapper:
    """JSON ↔ CameraSettingsData — plugin-internal use only."""

    @staticmethod
    def from_json(data: dict) -> CameraSettingsData:
        """Parse from the nested JSON format used by the repository."""
        pre   = data.get("Preprocessing",      {})
        cal   = data.get("Calibration",        {})
        bri   = data.get("Brightness Control", {})
        aruco = data.get("Aruco",              {})

        points: List[Tuple[int, int]] = []
        for i in range(1, 5):
            pt = bri.get(f"Brightness area point {i}")
            if pt:
                points.append((int(pt[0]), int(pt[1])))

        return CameraSettingsData(
            index                   = data.get("Index",                    0),
            width                   = data.get("Width",                    1280),
            height                  = data.get("Height",                   720),
            skip_frames             = data.get("Skip frames",              30),
            capture_position_offset = data.get("Capture position offset",  -4),
            contour_detection       = data.get("Contour detection",        True),
            draw_contours           = data.get("Draw contours",            True),
            threshold               = data.get("Threshold",                150),
            threshold_pickup_area   = data.get("Threshold pickup area",    200),
            epsilon                 = data.get("Epsilon",                  0.05),
            min_contour_area        = data.get("Min contour area",         1000.0),
            max_contour_area        = data.get("Max contour area",         10_000_000.0),
            gaussian_blur           = pre.get("Gaussian blur",             True),
            blur_kernel_size        = pre.get("Blur kernel size",          3),
            threshold_type          = pre.get("Threshold type",            "binary_inv"),
            dilate_enabled          = pre.get("Dilate enabled",            True),
            dilate_kernel_size      = pre.get("Dilate kernel size",        3),
            dilate_iterations       = pre.get("Dilate iterations",         2),
            erode_enabled           = pre.get("Erode enabled",             True),
            erode_kernel_size       = pre.get("Erode kernel size",         3),
            erode_iterations        = pre.get("Erode iterations",          4),
            chessboard_width        = cal.get("Chessboard width",          32),
            chessboard_height       = cal.get("Chessboard height",         20),
            square_size_mm          = cal.get("Square size (mm)",          25.0),
            calibration_skip_frames = cal.get("Skip frames",               30),
            brightness_auto         = bri.get("Enable auto adjust",        True),
            brightness_kp           = bri.get("Kp",                        0.0),
            brightness_ki           = bri.get("Ki",                        0.2),
            brightness_kd           = bri.get("Kd",                        0.05),
            target_brightness       = bri.get("Target brightness",         200.0),
            brightness_area_points  = points,
            aruco_enabled           = aruco.get("Enable detection",        False),
            aruco_dictionary        = aruco.get("Dictionary",              "DICT_4X4_1000"),
            aruco_flip_image        = aruco.get("Flip image",              False),
        )

    @staticmethod
    def to_json(data: CameraSettingsData) -> dict:
        """Serialize to the nested JSON format used by the repository."""
        bri: dict = {
            "Enable auto adjust": data.brightness_auto,
            "Kp":                 data.brightness_kp,
            "Ki":                 data.brightness_ki,
            "Kd":                 data.brightness_kd,
            "Target brightness":  data.target_brightness,
        }
        for i, pt in enumerate(data.brightness_area_points[:4], start=1):
            bri[f"Brightness area point {i}"] = list(pt)

        return {
            "Index":                   data.index,
            "Width":                   data.width,
            "Height":                  data.height,
            "Skip frames":             data.skip_frames,
            "Capture position offset": data.capture_position_offset,
            "Contour detection":       data.contour_detection,
            "Draw contours":           data.draw_contours,
            "Threshold":               data.threshold,
            "Threshold pickup area":   data.threshold_pickup_area,
            "Epsilon":                 data.epsilon,
            "Min contour area":        data.min_contour_area,
            "Max contour area":        data.max_contour_area,
            "Preprocessing": {
                "Gaussian blur":      data.gaussian_blur,
                "Blur kernel size":   data.blur_kernel_size,
                "Threshold type":     data.threshold_type,
                "Dilate enabled":     data.dilate_enabled,
                "Dilate kernel size": data.dilate_kernel_size,
                "Dilate iterations":  data.dilate_iterations,
                "Erode enabled":      data.erode_enabled,
                "Erode kernel size":  data.erode_kernel_size,
                "Erode iterations":   data.erode_iterations,
            },
            "Calibration": {
                "Chessboard width":  data.chessboard_width,
                "Chessboard height": data.chessboard_height,
                "Square size (mm)":  data.square_size_mm,
                "Skip frames":       data.calibration_skip_frames,
            },
            "Brightness Control": bri,
            "Aruco": {
                "Enable detection": data.aruco_enabled,
                "Dictionary":       data.aruco_dictionary,
                "Flip image":       data.aruco_flip_image,
            },
        }

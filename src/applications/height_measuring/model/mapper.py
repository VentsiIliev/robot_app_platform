from copy import deepcopy

from src.engine.robot.height_measuring.settings import HeightMeasuringModuleSettings


class HeightMeasuringSettingsMapper:

    @staticmethod
    def to_flat_dict(s: HeightMeasuringModuleSettings) -> dict:
        det  = s.detection
        cal  = s.calibration
        meas = s.measuring
        return {
            "min_intensity":          det.min_intensity,
            "blur_kernel_size":       det.gaussian_blur_kernel[0],
            "gaussian_blur_sigma":    det.gaussian_blur_sigma,
            "default_axis":           det.default_axis,
            "detection_delay_ms":     det.detection_delay_ms,
            "image_capture_delay_ms": det.image_capture_delay_ms,
            "detection_samples":      det.detection_samples,
            "max_detection_retries":  det.max_detection_retries,
            "step_size_mm":               cal.step_size_mm,
            "num_iterations":             cal.num_iterations,
            "calibration_velocity":       cal.calibration_velocity,
            "calibration_acceleration":   cal.calibration_acceleration,
            "movement_threshold":         cal.movement_threshold,
            "movement_timeout":           cal.movement_timeout,
            "cal_delay_ms":               cal.delay_between_move_detect_ms,
            "calibration_max_attempts":   cal.calibration_max_attempts,
            "max_polynomial_degree":      cal.max_polynomial_degree,
            "measurement_velocity":       meas.measurement_velocity,
            "measurement_acceleration":   meas.measurement_acceleration,
            "measurement_threshold":      meas.measurement_threshold,
            "measurement_timeout":        meas.measurement_timeout,
            "meas_delay_ms":              meas.delay_between_move_detect_ms,
        }

    @staticmethod
    def from_flat_dict(flat: dict, base: HeightMeasuringModuleSettings) -> HeightMeasuringModuleSettings:
        s    = deepcopy(base)
        det  = s.detection
        cal  = s.calibration
        meas = s.measuring

        det.min_intensity          = float(flat.get("min_intensity",          det.min_intensity))
        k = int(flat.get("blur_kernel_size", det.gaussian_blur_kernel[0]))
        if k % 2 == 0:
            k += 1
        det.gaussian_blur_kernel   = (k, k)
        det.gaussian_blur_sigma    = float(flat.get("gaussian_blur_sigma",    det.gaussian_blur_sigma))
        det.default_axis           = str(flat.get("default_axis",             det.default_axis))
        det.detection_delay_ms     = int(flat.get("detection_delay_ms",       det.detection_delay_ms))
        det.image_capture_delay_ms = int(flat.get("image_capture_delay_ms",   det.image_capture_delay_ms))
        det.detection_samples      = int(flat.get("detection_samples",        det.detection_samples))
        det.max_detection_retries  = int(flat.get("max_detection_retries",    det.max_detection_retries))

        cal.step_size_mm                 = float(flat.get("step_size_mm",             cal.step_size_mm))
        cal.num_iterations               = int(flat.get("num_iterations",             cal.num_iterations))
        cal.calibration_velocity         = float(flat.get("calibration_velocity",     cal.calibration_velocity))
        cal.calibration_acceleration     = float(flat.get("calibration_acceleration", cal.calibration_acceleration))
        cal.movement_threshold           = float(flat.get("movement_threshold",       cal.movement_threshold))
        cal.movement_timeout             = float(flat.get("movement_timeout",         cal.movement_timeout))
        cal.delay_between_move_detect_ms = int(flat.get("cal_delay_ms",               cal.delay_between_move_detect_ms))
        cal.calibration_max_attempts     = int(flat.get("calibration_max_attempts",   cal.calibration_max_attempts))
        cal.max_polynomial_degree        = int(flat.get("max_polynomial_degree",      cal.max_polynomial_degree))

        meas.measurement_velocity        = float(flat.get("measurement_velocity",    meas.measurement_velocity))
        meas.measurement_acceleration    = float(flat.get("measurement_acceleration", meas.measurement_acceleration))
        meas.measurement_threshold       = float(flat.get("measurement_threshold",   meas.measurement_threshold))
        meas.measurement_timeout         = float(flat.get("measurement_timeout",     meas.measurement_timeout))
        meas.delay_between_move_detect_ms = int(flat.get("meas_delay_ms",            meas.delay_between_move_detect_ms))

        return s
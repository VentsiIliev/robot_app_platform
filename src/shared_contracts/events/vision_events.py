class VisionTopics:
    """Vision system and camera topics"""

    # Vision service state
    SERVICE_STATE = "vision-service/state"
    LATEST_IMAGE = "vision-system/latest-image"
    FPS = "vision-system/fps"
    CALIBRATION_IMAGE_CAPTURED = "vision-system/calibration-image-captured"
    # Camera and image processing
    BRIGHTNESS_REGION = "vision-system/brightness-region"
    THRESHOLD_REGION = "vision-system/threshold"
    CALIBRATION_FEEDBACK = "vision-system/calibration-feedback"
    THRESHOLD_IMAGE = "vision-system/threshold-image"
    AUTO_BRIGHTNESS = "vision-system/auto-brightness"
    AUTO_BRIGHTNESS_START = "vison-auto-brightness"
    AUTO_BRIGHTNESS_STOP = "vison-auto-brightness"
    TRANSFORM_TO_CAMERA_POINT = "vision-system/transform-to-camera-point"
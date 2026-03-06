class VisionTopics:
    """Vision vision_service and camera topics"""

    # Vision service state
    SERVICE_STATE = "vision-service/state"
    LATEST_IMAGE = "vision-vision_service/latest-image"
    FPS = "vision-vision_service/fps"
    CALIBRATION_IMAGE_CAPTURED = "vision-vision_service/calibration-image-captured"
    # Camera and image processing
    BRIGHTNESS_REGION = "vision-vision_service/brightness-region"
    THRESHOLD_REGION = "vision-vision_service/threshold"
    CALIBRATION_FEEDBACK = "vision-vision_service/calibration-feedback"
    THRESHOLD_IMAGE = "vision-vision_service/threshold-image"
    AUTO_BRIGHTNESS = "vision-vision_service/auto-brightness"
    AUTO_BRIGHTNESS_START = "vison-auto-brightness"
    AUTO_BRIGHTNESS_STOP = "vison-auto-brightness"
    TRANSFORM_TO_CAMERA_POINT = "vision-vision_service/transform-to-camera-point"
import logging
import threading
from dataclasses import dataclass
from enum import Enum

from src.shared_contracts.events.vision_events import VisionTopics

_logger = logging.getLogger(__name__)


# class VisionTopics:
#     """Vision vision_service and camera topics"""
#
#     # Vision service state
#     SERVICE_STATE = "vision-service/state"
#     LATEST_IMAGE = "vision-vision_service/latest-image"
#     FPS = "vision-vision_service/fps"
#     CALIBRATION_IMAGE_CAPTURED = "vision-vision_service/calibration-image-captured"
#     # Camera and image processing
#     BRIGHTNESS_REGION = "vision-vision_service/brightness-region"
#     THRESHOLD_REGION = "vision-vision_service/threshold"
#     CALIBRATION_FEEDBACK = "vision-vision_service/calibration-feedback"
#     THRESHOLD_IMAGE = "vision-vision_service/threshold-image"
#     AUTO_BRIGHTNESS = "vision-vision_service/auto-brightness"
#     AUTO_BRIGHTNESS_START = "vison-auto-brightness"
#     AUTO_BRIGHTNESS_STOP = "vison-auto-brightness"
#     TRANSFORM_TO_CAMERA_POINT = "vision-vision_service/transform-to-camera-point"

class SubscriptionManager:

    def __init__(self, vision_system,messaging_service):
        self.vision_system = vision_system
        self.messaging_service = messaging_service
        self.subscriptions = {}

    def subscribe_to_threshold_update(self):
        self.messaging_service.subscribe(VisionTopics.THRESHOLD_REGION, self.vision_system.on_threshold_update)
        self.subscriptions[VisionTopics.THRESHOLD_REGION] = self.vision_system.on_threshold_update

    def subscribe_to_auto_brightness_toggle(self):
        cb = self.vision_system._brightness_service.on_brightness_toggle
        self.messaging_service.subscribe(VisionTopics.AUTO_BRIGHTNESS, cb)
        self.subscriptions[VisionTopics.AUTO_BRIGHTNESS] = cb

    def subscribe_all(self):
        self.subscribe_to_threshold_update()
        self.subscribe_to_auto_brightness_toggle()


class MessagePublisher:
    def __init__(self,messaging_service):
        self.messaging_service= messaging_service
        self.latest_image_topic = VisionTopics.LATEST_IMAGE
        self.calibration_image_captured_topic = VisionTopics.CALIBRATION_IMAGE_CAPTURED
        self.thresh_image_topic = VisionTopics.THRESHOLD_IMAGE
        self.stateTopic = VisionTopics.SERVICE_STATE
        self.topic = VisionTopics.CALIBRATION_FEEDBACK

    def publish_latest_image(self,image):
        self.messaging_service.publish(self.latest_image_topic, {"image": image})

    def publish_calibration_image_captured(self,calibration_images):
        self.messaging_service.publish(self.calibration_image_captured_topic, calibration_images)

    def publish_thresh_image(self,thresh_image):
        self.messaging_service.publish(self.thresh_image_topic, thresh_image)

    def publish_state(self,state):
        # _logger.info(f"[VisionMessagePublisher] Publishing vision service state on topic {self.stateTopic}:", state)

        self.messaging_service.publish(self.stateTopic, state)

    def publish_calibration_feedback(self,feedback):
        self.messaging_service.publish(self.topic, feedback)
# ==========================================================
# Service State (also used as System State)
# Higher numeric value = higher priority
# ==========================================================

class ServiceState(Enum):
    UNKNOWN = 0
    INITIALIZING = 1
    IDLE = 2
    STARTED = 3
    PAUSED = 4
    STOPPED = 5
    ERROR = 6


# ==========================================================
# Message Model
# ==========================================================

@dataclass
class ServiceStateMessage:
    id: str
    state: ServiceState

    def to_dict(self):
        return {
            "id": self.id,
            "state": self.state.name
        }

# ==========================================================
# Service State Manager (per service)
# ==========================================================

class StateManager:
    """
    Used inside individual services.
    Publishes service state changes.
    """

    def __init__(self,
                 service_id: str,
                 initial_state: ServiceState,
                 message_publisher):

        self.service_id = service_id
        self.state = initial_state
        self.message_publisher = message_publisher
        self._lock = threading.Lock()

    # ------------------------------------------------------

    def update_state(self, new_state: ServiceState):
        with self._lock:
            # if self.state == new_state:
            #     return

            self.state = new_state
            self._publish_state()

    # ------------------------------------------------------

    def _publish_state(self):
        message = ServiceStateMessage(
            id=self.service_id,
            state=self.state
        ).to_dict()

        self.message_publisher.publish_state(message)
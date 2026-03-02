import sys
import logging
import threading
import time

from PyQt6.QtWidgets import QApplication, QMainWindow

from src.applications.broker_debug.broker_debug_factory import BrokerDebugFactory
from src.applications.broker_debug.service.stub_broker_debug_service import StubBrokerDebugService
from src.engine.core.messaging_service import MessagingService
from src.shared_contracts.events.vision_events import VisionTopics


def _simulate_traffic(messaging: MessagingService, stop: threading.Event) -> None:
    import random
    topics = [
        VisionTopics.LATEST_IMAGE,
        VisionTopics.SERVICE_STATE,
        VisionTopics.THRESHOLD_IMAGE,
        "process/glue/state",
        "weight-cell/reading",
    ]
    while not stop.is_set():
        t = random.choice(topics)
        messaging.publish(t, {"value": random.randint(0, 100)})
        stop.wait(1.5)


def run_standalone():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    )

    app       = QApplication(sys.argv)
    messaging = MessagingService()

    stop_event = threading.Event()
    thread = threading.Thread(
        target=_simulate_traffic, args=(messaging, stop_event),
        daemon=True, name="sim-traffic",
    )
    thread.start()

    service = BrokerDebugApplicationService(messaging)
    widget  = BrokerDebugFactory(messaging).build(service)

    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1280, 900)
    window.setWindowTitle("Broker Debug — Standalone")
    window.destroyed.connect(stop_event.set)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    from src.applications.broker_debug.service.broker_debug_application_service import BrokerDebugApplicationService
    run_standalone()
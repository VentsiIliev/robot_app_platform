import logging
import time

from src.engine.core.message_broker import MessageBroker
from src.engine.robot.services.robot_state_snapshot import RobotStateSnapshot
from src.engine.vision.vision_service import VisionService
from src.shared_contracts.events.robot_events import RobotTopics

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s")

from src.engine.robot.drivers.fairino.test_robot import TestRobotWrapper
from src.robot_apps.app_builder import AppBuilder
from src.robot_apps.glue.glue_robot_app import GlueRobotApp


def on_robot_state(snapshot: RobotStateSnapshot) -> None:       # ← named function, stays alive
    print(f"pos={snapshot.position}  vel={snapshot.velocity}  acc={snapshot.acceleration}")


broker = MessageBroker()
broker.subscribe(RobotTopics.STATE, on_robot_state)             # ← strong ref, won't be GC'd


app = (
    AppBuilder()
    .with_robot(TestRobotWrapper())
    .register(VisionService, lambda ctx: VisionService())
    .build(GlueRobotApp)
)



# add while look to run the app for 10 seconds
current_time = time.time()
while time.time() - current_time < 1:
    pass

app.stop()
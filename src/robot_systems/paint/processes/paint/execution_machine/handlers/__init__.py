from src.robot_systems.paint.processes.paint.execution_machine.handlers.calibration_wait_camera_settle_handler import (
    handle_calibration_wait_camera_settle,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.capture_handler import (
    handle_capture_workpiece,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.completed_handler import (
    handle_completed,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff_handler import (
    handle_dropoff,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.edge_cleanup_handler import (
    handle_edge_cleanup,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.error_handler import (
    handle_error,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.execution_handler import (
    handle_execute_paint,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.idle_handler import (
    handle_idle,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_capture_handler import (
    handle_magazine_capture,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_execute_pickup_release_handler import (
    handle_magazine_execute_pickup_release,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load_compat_handler import (
    handle_magazine_load,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_move_to_calibration_handler import (
    handle_magazine_move_to_calibration,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_move_to_magazine_handler import (
    handle_magazine_move_to_magazine,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_prepare_pickup_release_handler import (
    handle_magazine_prepare_pickup_release,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_wait_camera_settle_handler import (
    handle_magazine_wait_camera_settle,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.paint_contact_handler import (
    handle_paint_contact,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.pause_handler import (
    handle_paused,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.pickup_handler import (
    handle_pickup,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.plan_handler import (
    handle_build_execution_plan,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.preparation_handler import (
    handle_prepare_workpiece,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.prepare_dropoff_handler import (
    handle_prepare_dropoff,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.post_return_handler import (
    handle_post_return,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.startup_handler import (
    handle_starting,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.stopped_handler import (
    handle_stopped,
)

__all__ = [
    "handle_build_execution_plan",
    "handle_calibration_wait_camera_settle",
    "handle_capture_workpiece",
    "handle_completed",
    "handle_dropoff",
    "handle_edge_cleanup",
    "handle_error",
    "handle_execute_paint",
    "handle_idle",
    "handle_magazine_capture",
    "handle_magazine_execute_pickup_release",
    "handle_magazine_load",
    "handle_magazine_move_to_calibration",
    "handle_magazine_move_to_magazine",
    "handle_magazine_prepare_pickup_release",
    "handle_magazine_wait_camera_settle",
    "handle_paint_contact",
    "handle_paused",
    "handle_pickup",
    "handle_post_return",
    "handle_prepare_dropoff",
    "handle_prepare_workpiece",
    "handle_starting",
    "handle_stopped",
]

from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.calibration_wait_camera_settle_handler import (
    handle_calibration_wait_camera_settle,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.capture_handler import (
    handle_capture_workpiece,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.completed_handler import (
    handle_completed,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handler import (
    handle_dropoff,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.edge_cleanup_handler import (
    handle_edge_cleanup,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.error_handler import (
    handle_error,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.execution_handler import (
    handle_execute_paint,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.idle_handler import (
    handle_idle,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_capture_handler import (
    handle_magazine_capture,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_execute_pickup_release_handler import (
    handle_magazine_execute_pickup_release,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_load_compat_handler import (
    handle_magazine_load,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_move_to_calibration_handler import (
    handle_magazine_move_to_calibration,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_move_to_magazine_handler import (
    handle_magazine_move_to_magazine,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_prepare_pickup_release_handler import (
    handle_magazine_prepare_pickup_release,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_wait_camera_settle_handler import (
    handle_magazine_wait_camera_settle,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.paint_contact_handler import (
    handle_paint_contact,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.pause_handler import (
    handle_paused,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.pickup_handler import (
    handle_pickup,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.plan_handler import (
    handle_build_execution_plan,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.preparation_handler import (
    handle_prepare_workpiece,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.prepare_dropoff_handler import (
    handle_prepare_dropoff,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.post_return_handler import (
    handle_post_return,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.startup_handler import (
    handle_starting,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.stopped_handler import (
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

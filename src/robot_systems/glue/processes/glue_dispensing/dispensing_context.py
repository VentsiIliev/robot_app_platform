from __future__ import annotations
import threading
from typing import Optional, List, Tuple, Any


class DispensingContext:
    def __init__(self) -> None:
        self.stop_event:  threading.Event = threading.Event()
        self.run_allowed: threading.Event = threading.Event()
        self.run_allowed.set()
        self.paused_from_state = None
        self.reset()

    def reset(self) -> None:
        self.paths:                    Optional[List[Tuple[Any, Any]]] = None
        self.spray_on:                 bool  = False
        self.motor_service             = None   # IMotorService
        self.generator                 = None   # IGeneratorController
        self.robot_service             = None   # IRobotService
        self.resolver                  = None   # IGlueTypeResolver
        self.pump_controller           = None   # GluePumpController
        self.state_machine             = None   # set by DispensingMachineFactory
        self.current_path_index:       int   = 0
        self.current_point_index:      int   = 0
        self.target_point_index:       int   = 0
        self.is_resuming:              bool  = False
        self.generator_started:        bool  = False
        self.motor_started:            bool  = False
        self.current_settings:         Optional[dict] = None
        self.current_path:             Optional[list] = None
        self.paused_from_state                = None
        self.pump_thread                      = None
        self.pump_ready_event                 = None
        self.operation_just_completed: bool  = False
        # robot motion params (populated from GlueDispensingConfig)
        self.robot_tool:               int   = 0
        self.robot_user:               int   = 0
        self.global_velocity:          float = 10.0
        self.global_acceleration:      float = 30.0

    def save_progress(self, path_index: int, point_index: int) -> None:
        self.current_path_index  = path_index
        self.current_point_index = point_index

    def has_valid_context(self) -> bool:
        return self.paths is not None and len(self.paths) > 0

    def get_motor_address_for_current_path(self) -> int:
        from src.robot_systems.glue.settings.glue import GlueSettingKey
        if not self.current_settings:
            return 0
        glue_type = self.current_settings.get(GlueSettingKey.GLUE_TYPE.value)
        if not glue_type:
            return -1
        if self.resolver is None:
            return -1
        return self.resolver.resolve(glue_type)


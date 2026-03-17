from __future__ import annotations

from src.robot_systems.glue.processes.glue_dispensing.dispensing_path import DispensingPathEntry


class DispensingPathOps:
    def __init__(self, context) -> None:
        self._context = context

    def has_remaining_paths(self) -> bool:
        context = self._context
        return context.paths is not None and context.current_path_index < len(context.paths)

    def get_current_path_entry(self):
        context = self._context
        raw_entry = context.paths[context.current_path_index]
        entry = DispensingPathEntry.from_raw(raw_entry)
        context.paths[context.current_path_index] = entry
        return entry

    def load_current_path(self) -> None:
        context = self._context
        entry = self.get_current_path_entry()
        context.current_entry = entry
        context.current_path = entry.points
        context.current_settings = entry.settings
        context.current_point_index = 0
        context.reset_segment_trajectory_state()

    def restart_current_path(self) -> None:
        self.load_current_path()

    def load_current_path_from_progress(self) -> None:
        context = self._context
        entry = self.get_current_path_entry()
        context.current_entry = entry
        context.current_path = entry.sliced_from(context.current_point_index)
        context.current_settings = entry.settings
        context.current_segment_start_index = context.current_point_index
        context.segment_trajectory_submitted = False
        context.segment_trajectory_completed = False

    def resume_current_path_from_progress(self) -> None:
        self.load_current_path_from_progress()

    def has_current_path_loaded(self) -> bool:
        context = self._context
        return bool(context.current_settings and context.current_path)

    def get_current_path_start_point(self):
        return self._context.current_path[0]

    def get_current_path_end_point(self):
        return self._context.current_path[-1]

    def advance_to_next_path(self) -> None:
        context = self._context
        context.current_path_index += 1
        context.current_point_index = 0
        context.reset_segment_trajectory_state()

    def skip_current_path(self) -> None:
        self.advance_to_next_path()

    def mark_first_point_reached(self) -> None:
        context = self._context
        if context.current_path is None:
            context.current_point_index = 0
            return
        context.current_point_index = min(1, len(context.current_path))
        context.current_segment_start_index = context.current_point_index
        context.segment_trajectory_submitted = False
        context.segment_trajectory_completed = False

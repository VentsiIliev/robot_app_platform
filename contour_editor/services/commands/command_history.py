from typing import List, Optional
from .base_command import Command


class CommandHistory:
    _instance = None

    def __init__(self, max_history=100):
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self._max_history = max_history

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = CommandHistory()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    def execute(self, command: Command):
        command.execute()
        if self._undo_stack and self._undo_stack[-1].can_merge_with(command):
            self._undo_stack[-1].merge_with(command)
        else:
            self._undo_stack.append(command)
            if len(self._undo_stack) > self._max_history:
                self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        command = self._redo_stack.pop()
        command.execute()
        self._undo_stack.append(command)
        return True

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def get_undo_description(self) -> Optional[str]:
        if self._undo_stack:
            return self._undo_stack[-1].get_description()
        return None

    def get_redo_description(self) -> Optional[str]:
        if self._redo_stack:
            return self._redo_stack[-1].get_description()
        return None

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()

    def get_history_size(self) -> int:
        return len(self._undo_stack)


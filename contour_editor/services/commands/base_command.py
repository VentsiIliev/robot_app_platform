from abc import ABC, abstractmethod


class Command(ABC):
    def __init__(self):
        self._executed = False

    @abstractmethod
    def execute(self):
        pass

    @abstractmethod
    def undo(self):
        pass

    @abstractmethod
    def get_description(self):
        pass

    def can_merge_with(self, other):
        return False

    def merge_with(self, other):
        raise NotImplementedError("This command does not support merging")


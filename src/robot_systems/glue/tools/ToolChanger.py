from dataclasses import dataclass
from modules.shared.tools.enums.Gripper import Gripper


SLOT_TOOL_MAP = {
    10: 0,
    11: 1,
    12: 2,
    13: 3,
    14: 4
}

@dataclass
class SlotConfig:
    id: int
    occupied: int
    reservedFor: Gripper

class ToolChanger:

    STATUS_AVAILABLE = -1
    STATUS_OCCUPIED = 0

    def __init__(self, slot_tool_map=None):

        self.slot_tool_map = slot_tool_map or SLOT_TOOL_MAP

        self.slots: dict[int, SlotConfig] = {}
        self.add_slot(SlotConfig(10, self.STATUS_AVAILABLE, Gripper.BELT))
        self.add_slot(SlotConfig(11, self.STATUS_AVAILABLE, Gripper.SINGLE))
        self.add_slot(SlotConfig(12, self.STATUS_AVAILABLE, Gripper.DOUBLE))
        self.add_slot(SlotConfig(13, self.STATUS_AVAILABLE, Gripper.MOCK3))
        self.add_slot(SlotConfig(14, self.STATUS_AVAILABLE, Gripper.MOCK4))

    def add_slot(self, slot_config: SlotConfig):
        self.slots[slot_config.id] = slot_config

    def _setSlotOccupied(self, slotId, status):
        if slotId in self.slots and status in [self.STATUS_AVAILABLE, self.STATUS_OCCUPIED]:
            self.slots[slotId].occupied = status
        else:
            raise ValueError("Invalid slot ID or status. Use -1 or 0.")

    def setSlotNotAvailable(self, slotId):
        self._setSlotOccupied(slotId, self.STATUS_OCCUPIED)

    def setSlotAvailable(self, slotId):
        self._setSlotOccupied(slotId, self.STATUS_AVAILABLE)

    def isSlotOccupied(self, slotId):
        print("Slot ID:", slotId)
        occupied = self.slots[slotId].occupied == self.STATUS_OCCUPIED
        print("Occupied:", occupied)
        return occupied

    def getOccupiedSlots(self):
        return [slotId for slotId, slot in self.slots.items()
                if slot.occupied == self.STATUS_OCCUPIED]

    def getEmptySlots(self):
        return [slotId for slotId, slot in self.slots.items()
                if slot.occupied == self.STATUS_AVAILABLE]

    def getReservedFor(self, slotId):
        return self.slots[slotId].reservedFor

    def isSlotReserved(self, slotId):
        return self.slots[slotId].reservedFor is not None

    def getSlotToolMap(self):
        return self.slot_tool_map

    def getSlotIds(self):
        return list(self.slots.keys())

    def getReservedForIds(self):
        return [int(slot.reservedFor.value) for slot in self.slots.values()]

    def getSlotIdByGrippedId(self, gripperId: int):
        print("getSlotIdByGrippedId Gripper ID:", gripperId)
        for slotId, slot in self.slots.items():
            if int(slot.reservedFor.value) == gripperId:
                return slotId

        print(f"Cannot find slot for gripper {gripperId} (type={type(gripperId)}).")
        return None

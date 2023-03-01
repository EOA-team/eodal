from enum import Enum


class ProcessingLevels(Enum):
    """
    possible processing levels of remotely sensed data
    """

    L1A = "Level-1A"
    L1B = "Level-1B"
    L1C = "Level-1C"
    L2A = "Level-2A"
    L2B = "Level-2B"
    L3 = "Level-3"
    L4 = "Level-4"
    UNKNOWN = "UNKNOWN"

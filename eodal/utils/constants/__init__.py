
from enum import Enum

class ProcessingLevels(Enum):
    """
    possible processing levels of remotely sensed data
    """
    L1A = 'LEVEL1A'
    L1B = 'LEVEL1B'
    L1C = 'LEVEL1C'
    L2A = 'LEVEL2A'
    L2B = 'LEVEL2B'
    L3 = 'LEVEL3'
    L4 = 'LEVEL4'
    UNKNOWN = 'UNKNOWN'

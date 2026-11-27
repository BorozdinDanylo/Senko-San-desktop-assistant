from enum import IntEnum


class Version(IntEnum):
    V1 = 1
    V2 = 2


class DataType(IntEnum):
    AUDIO = 1
    TEXT = 2
    RESPONSE = 3


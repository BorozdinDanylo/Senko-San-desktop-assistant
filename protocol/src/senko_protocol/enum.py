from enum import IntEnum


class Version(IntEnum):
    V1 = 1
    V2 = 2


class DataType(IntEnum):
    AUDIO = 1
    TEXT = 2
    RESPONSE = 3
    COMMAND = 4
    REGISTER_CLIENT = 5


class Commands(IntEnum):
    STATUS = 1
    MICROPHONE = 2


class EmptyAction(IntEnum):
    EMPTY = 0


class MicrophoneActions(IntEnum):
    OFF = 1
    ON = 2
    SWITCH = 3


type Actions = (
    EmptyAction
    | MicrophoneActions
)


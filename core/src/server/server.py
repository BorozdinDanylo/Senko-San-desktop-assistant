from .transport import Connector
from .connection import create_connector
from core.components import Events
from senko_protocol.enum import DataType, Commands, Actions
from senko_protocol.meta import SingletonMeta
import struct



class Server(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self.connection: Connector = create_connector()

    def start(self) -> None:
        self.connection.start()

        Events.on_give_audio.subscribe(self.send_audio_answer)

    async def close(self) -> None:
        await self.connection.close()

        Events.on_give_audio.unsubscribe(self.send_audio_answer)

    async def send_audio_answer(self, answer: bytes) -> None:
        await self.connection.send(answer, DataType.AUDIO)

    async def send_command(self, command: Commands, action: Actions) -> None:
        body: bytes = struct.pack(
            "!BB",
            command,
            action
        )
        await self.connection.send(body, DataType.COMMAND)

from .transport import Connector
from .connection import create_connector
from core.components import Events
from senko_protocol.enum import DataType


class Server:
    def __init__(self):
        self.connection: Connector = create_connector()

    def start(self):
        self.connection.start()

        Events.on_give_audio.subscribe(self.send_audio_answer)

    async def close(self):
        await self.connection.close()

        Events.on_give_audio.unsubscribe(self.send_audio_answer)

    async def send_audio_answer(self, answer: bytes):
        await self.connection.send(answer, DataType.AUDIO)

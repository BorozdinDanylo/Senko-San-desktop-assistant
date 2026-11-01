from .transport import Connector
from .connection import create_connector
from senko_protocol.typing import AudioArray


class Server:
    def __init__(self):
        self.connection: Connector = create_connector()

    def start(self):
        self.connection.start()

    async def close(self):
        await self.connection.close()

    async def send_audio_answer(self, answer: AudioArray):
        await self.connection.send(answer.tobytes())

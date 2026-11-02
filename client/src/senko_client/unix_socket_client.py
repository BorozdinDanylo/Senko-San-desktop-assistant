from senko_protocol.model import Response, Header, Request
from senko_protocol.enum import Version, DataType
from senko_protocol.typing import AudioArray
from components.event import Events
from conection.unix_socket import UnixSocket
import asyncio


class SenkoClient:
    def __init__(self):
        self.unix_socket = UnixSocket()

        Events.on_audio_complete.subscribe(self.send_audio)

    async def send_audio(self, audio: AudioArray):
        audio_bytes = audio.tobytes()

        response: Response = await self.unix_socket.fetch(
            audio_bytes,
            DataType.AUDIO
        )

        print(response)

    async def start(self):
        await self.unix_socket.connect()
        asyncio.create_task(self.unix_socket.listen())

    async def stop(self):
        await self.unix_socket.disconnect()

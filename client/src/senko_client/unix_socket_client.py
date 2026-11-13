from senko_protocol.model import Response
from senko_protocol.enum import DataType
from senko_protocol.typing import AudioArray
from senko_client.components import Events
from conection.unix_socket import UnixSocket


class SenkoClient:
    def __init__(self) -> None:
        self.unix_socket: UnixSocket = UnixSocket()

        Events.on_audio_complete.subscribe(self.send_audio)

    async def send_audio(self, audio: AudioArray) -> None:
        audio_bytes: bytes = audio.tobytes()

        response: Response = await self.unix_socket.fetch(
            audio_bytes,
            DataType.AUDIO
        )

        print(response)

    async def start(self) -> None:
        await self.unix_socket.connect()

    async def stop(self) -> None:
        await self.unix_socket.disconnect()

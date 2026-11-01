from senko_protocol.model import Response, Header, Request
from senko_protocol.enum import Version, DataType
from senko_protocol.typing import AudioArray
from components.event import Events
from conection.unix_socket import UnixSocket


class SenkoClient:
    def __init__(self):
        self.unix_socket = UnixSocket()
        self.unix_socket.connect()

        Events.on_audio_complete.subscribe(self.send_audio)

    async def send_audio(self, audio: AudioArray):
        audio_bytes = audio.tobytes()

        header = Header(
            version=Version.V1,
            type=DataType.AUDIO,
            body_length=len(audio_bytes),
        )

        response: Response = await self.unix_socket.request(
            Request(
                header=header,
                body=audio_bytes,
            )
        )

        print(response)

    async def start(self):
        await self.unix_socket.connect()

    async def stop(self):
        await self.unix_socket.disconnect()

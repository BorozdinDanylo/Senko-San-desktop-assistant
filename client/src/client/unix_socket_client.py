from senko_protocol.model import Response, Header, Request
from senko_protocol.enum import Version, DataType
from components.event import Events
from conection.unix_socket import UnixSocket
import numpy as np


class SenkoClient:
    def __init__(self):
        self.unix_socket = UnixSocket()

        Events.on_audio_complete.subscribe(self.send_audio)

    async def send_audio(self, audio: np.ndarray):
        audio_bytes = audio.tobytes()

        header = Header(
            version=Version.V1,
            type=DataType.AUDIO,
            body_length=len(audio_bytes),
        )

        response: Response = await self.unix_socket.send_message(
            Request(
                header=header,
                body=audio_bytes,
            )
        )

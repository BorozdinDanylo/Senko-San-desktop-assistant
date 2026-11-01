from pipeline.components import Events
from senko_protocol.model import Header, ResponseBody, model_to_bytes
from senko_protocol.enum import Version, DataType
from senko_protocol.path import SOCKET_PATH
from senko_protocol.meta import SingletonMeta
from senko_protocol.const import MAX_AUDIO_SIZE
from senko_protocol.typeing import AudioArray
from .connctor import Connector
from pathlib import Path
import numpy as np
import struct
import asyncio


class UnixSocket(Connector, metaclass=SingletonMeta):
    def __init__(self):
        super().__init__()

        self._worker: asyncio.Task | None = None

    async def handle_client(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
    ):
        try:
            while True:
                version_code, = await reader.readexactly(1)
                try:
                    version = Version(version_code)
                except ValueError:
                    await self.response("Unsupported protocol version", writer)
                    return

                match version:
                    case Version.V1:
                        header = await reader.readexactly(5)
                        data_type, message_length = struct.unpack("!BI", header)

                match data_type:
                    case DataType.AUDIO:
                        if message_length > MAX_AUDIO_SIZE:
                            await self.response("Audio message too large", writer)
                            return

                        audio_bytes: bytes = await reader.readexactly(message_length)
                        audio: AudioArray = np.frombuffer(audio_bytes, dtype=np.float32)
                        try:
                            await Events.on_audio_receiving.emit(audio)
                        except Exception as e:
                            await self.response(f"Error receiving audio {e}", writer)
                            return

                        await self.response("Audio has been processed", writer)

        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    @staticmethod
    async def response(response_message: str, writer: asyncio.StreamWriter, version: Version = Version.V1, status_code: int = 200):
        body = ResponseBody(
            status_code=status_code,
            message=response_message,
        )
        body_bytes = model_to_bytes(body)

        header = Header(
            version=version,
            type=DataType.RESPONSE,
            body_length=len(body_bytes),
        )
        header_bytes = struct.pack(
            "!BBI",
            header.version,
            header.type,
            header.body_length,
        )

        writer.write(header_bytes + body_bytes)

    async def run(self):
        Path(SOCKET_PATH).unlink(missing_ok=True)

        server = await asyncio.start_unix_server(
            self.handle_client,
            path=SOCKET_PATH,
        )

        async with server:
            await server.serve_forever()

    def start(self):
        if self._worker is not None:
            return

        self._worker = asyncio.create_task(self.run())

    async def close(self):
        if self._worker is None:
            return

        self._worker.cancel()

        try:
            await self._worker
        except asyncio.CancelledError:
            pass





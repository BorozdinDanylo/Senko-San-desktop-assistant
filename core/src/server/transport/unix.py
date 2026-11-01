from pipeline.components import Events
from senko_protocol.model import Header, ResponseBody, model_to_bytes
from senko_protocol.enum import Version, DataType
from senko_protocol.path import SOCKET_PATH
from senko_protocol.meta import SingletonMeta
from senko_protocol.const import MAX_AUDIO_SIZE
from senko_protocol.typing import AudioArray
from .connctor import Connector
from pathlib import Path
import numpy as np
import struct
import asyncio
import os


class UnixSocket(Connector, metaclass=SingletonMeta):
    def __init__(self):
        super().__init__()

        self._reader = None
        self._writer = None

        self._worker: asyncio.Task | None = None

    @property
    def reader(self) -> asyncio.StreamReader:
        if self._reader is None:
            raise RuntimeError("Server is not connected")

        return self._reader

    @property
    def writer(self) -> asyncio.StreamWriter:
        if self._writer is None:
            raise RuntimeError("Server is not connected")

        return self._writer

    async def handle_client(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
    ):
        try:
            while True:
                self._reader = reader
                self._writer = writer

                version_code, = await reader.readexactly(1)
                try:
                    version = Version(version_code)
                except ValueError:
                    return

                data_type: DataType
                message_length: int
                request_id: str = ""

                match version:
                    case Version.V1:
                        header = await reader.readexactly(5)
                        data_type, message_length = struct.unpack("!BI", header)
                    case Version.V2:
                        header = await reader.readexactly(21)
                        data_type, message_length, request_id = struct.unpack("!BI16s", header)

                match data_type:
                    case DataType.AUDIO:
                        if message_length > MAX_AUDIO_SIZE:
                            await self.response("Audio message too large", request_id)
                            return

                        audio_bytes: bytes = await reader.readexactly(message_length)
                        audio: AudioArray = np.frombuffer(audio_bytes, dtype=np.float32)
                        try:
                            await Events.on_audio_receiving.emit(audio)
                        except Exception as e:
                            await self.response(f"Error receiving audio {e}", request_id)
                            return

                        await self.response("Audio has been processed", request_id)

        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def response(self, response_message: str, request_id: str, version: Version = Version.V1, status_code: int = 200):
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

        self.writer.write(header_bytes + body_bytes)

        print("Send Response")

    async def run(self):
        Path(SOCKET_PATH).unlink(missing_ok=True)

        server = await asyncio.start_unix_server(
            self.handle_client,
            path=SOCKET_PATH,
        )

        os.chmod(SOCKET_PATH, 0o660)

        async with server:
            await server.serve_forever()

    async def send(self, body_message: bytes, dtype: DataType, version: Version = Version.V1):
        header = Header(
            version=version,
            type=dtype,
            body_length=len(body_message),
        )
        header_bytes = struct.pack(
            "!BBI",
            header.version,
            header.type,
            header.body_length,
        )

        self.writer.write(header_bytes + body_message)
        await self.writer.drain()

    def start(self):
        if self._worker is not None:
            return

        self._worker = asyncio.create_task(self.run())

    async def close(self):
        if self._worker is None:
            return

        self._worker.cancel()

        self._reader = None
        self._writer = None

        try:
            await self._worker
        except asyncio.CancelledError:
            pass





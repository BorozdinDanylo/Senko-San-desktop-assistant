from core.components import Events
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
import uuid
import asyncio
import os


class UnixSocket(Connector, metaclass=SingletonMeta):
    def __init__(self):
        super().__init__()

        self._reader = None
        self._writer = None

        self._worker: asyncio.Task | None = None
        self._lock = asyncio.Lock()

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
                    print(version_code)
                    version = Version(version_code)
                except ValueError:
                    continue

                data_type: DataType
                message_length: int
                request_id: uuid.UUID | None = None

                match version:
                    case Version.V1:
                        header = await reader.readexactly(5)
                        data_type, message_length = struct.unpack("!BI", header)
                    case Version.V2:
                        header = await reader.readexactly(21)
                        data_type, message_length, request_bytes = struct.unpack("!BI16s", header)
                        request_id = uuid.UUID(bytes=request_bytes)
                        print(f"Got {request_id=}")

                match data_type:
                    case DataType.AUDIO:
                        if message_length > MAX_AUDIO_SIZE:
                            await self.response("Audio message too large", request_id)
                            return

                        audio_bytes: bytes = await reader.readexactly(message_length)
                        audio: AudioArray = np.frombuffer(audio_bytes, dtype=np.float32)
                        try:
                            await Events.on_audio_receiving.emit(audio)
                            print("Received Audio")
                        except Exception as e:
                            await self.response(f"Error receiving audio {e}", request_id)
                            return

                        await self.response("Audio has been processed", request_id)

        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def response(self, response_message: str, request_id: uuid.UUID | None, version: Version = Version.V2, status_code: int = 200):
        if version == Version.V1 or request_id is None:
            return

        body = ResponseBody(
            status_code=status_code,
            message=response_message,
        )
        body_bytes = model_to_bytes(body)

        header = Header(
            version=version,
            type=DataType.RESPONSE,
            body_length=len(body_bytes),
            request_id=request_id,
        )
        assert header.request_id is not None
        header_bytes = struct.pack(
            "!BBI16s",
            header.version,
            header.type,
            header.body_length,
            header.request_id.bytes
        )

        async with self._lock:
            self.writer.write(header_bytes + body_bytes)
            await self.writer.drain()

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

        async with self._lock:
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





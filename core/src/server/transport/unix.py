from core.components import Events
from senko_protocol.model import Header, ResponseBody, model_to_bytes
from senko_protocol.enum import Version, DataType, Commands, MicrophoneActions
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
    def __init__(self) -> None:
        super().__init__()

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

        self._worker: asyncio.Task[None] | None = None
        self._lock: asyncio.Lock = asyncio.Lock()

        self._clients: set[asyncio.Task[None]] = set()
        self._writers: set[asyncio.StreamWriter] = set()
        self._runtime_writers: set[asyncio.StreamWriter] = set()
        self._owns_socket: bool = False

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
    ) -> None:
        task: asyncio.Task[None] | None = asyncio.current_task()

        if task is not None:
            self._clients.add(task)

        self._writers.add(writer)

        try:
            while True:
                self._reader = reader
                self._writer = writer

                version_code, = await reader.readexactly(1)
                try:
                    print(version_code)
                    version: Version = Version(version_code)
                except ValueError:
                    continue

                data_type: DataType
                message_length: int
                request_id: uuid.UUID | None = None

                match version:
                    case Version.V1:
                        header: bytes = await reader.readexactly(5)
                        data_type, message_length = struct.unpack("!BI", header)
                    case Version.V2:
                        header = await reader.readexactly(21)
                        data_type, message_length, request_bytes = struct.unpack("!BI16s", header)
                        request_id = uuid.UUID(bytes=request_bytes)
                        print(f"Got {request_id=}")

                match data_type:
                    case DataType.REGISTER_CLIENT:
                        if message_length != 6:
                            return

                        registration: bytes = await reader.readexactly(message_length)

                        if registration != b"client":
                            return

                        self._runtime_writers.add(writer)

                    case DataType.COMMAND:
                        if message_length != 2:
                            await self.response("Invalid command length", request_id, status_code=400, writer=writer)
                            return

                        command_body: bytes = await reader.readexactly(message_length)
                        command_code: int
                        action_code: int
                        command_code, action_code = struct.unpack("!BB", command_body)

                        try:
                            command: Commands = Commands(command_code)

                            if command != Commands.MICROPHONE:
                                raise ValueError("Unsupported command")

                            MicrophoneActions(action_code)
                        except ValueError:
                            await self.response("Invalid command or action", request_id, status_code=400, writer=writer)
                            continue

                        delivered: bool = await self.forward_command(command_body)
                        await self.response(
                            "Command forwarded" if delivered else "No active Senko client",
                            request_id,
                            status_code=200 if delivered else 503,
                            writer=writer,
                        )

                    case DataType.AUDIO:
                        if message_length > MAX_AUDIO_SIZE:
                            await self.response("Audio message too large", request_id, writer=writer)
                            return

                        audio_bytes: bytes = await reader.readexactly(message_length)
                        audio: AudioArray = np.frombuffer(audio_bytes, dtype=np.float32)
                        try:
                            await Events.on_audio_receiving.emit(audio)
                            print("Received Audio")
                        except Exception as e:
                            await self.response(f"Error receiving audio {e}", request_id, writer=writer)
                            return

                        await self.response("Audio has been processed", request_id, writer=writer)

        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            self._writers.discard(writer)
            self._runtime_writers.discard(writer)

            if task is not None:
                self._clients.discard(task)

            if self._writer is writer:
                self._reader = None
                self._writer = None

            writer.close()

            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def response(self, response_message: str, request_id: uuid.UUID | None, version: Version = Version.V2, status_code: int = 200, *, writer: asyncio.StreamWriter | None = None) -> None:
        if version == Version.V1 or request_id is None:
            return

        body: ResponseBody = ResponseBody(
            status_code=status_code,
            message=response_message,
        )
        body_bytes: bytes = model_to_bytes(body)

        header: Header = Header(
            version=version,
            type=DataType.RESPONSE,
            body_length=len(body_bytes),
            request_id=request_id,
        )
        assert header.request_id is not None
        header_bytes: bytes = struct.pack(
            "!BBI16s",
            header.version,
            header.type,
            header.body_length,
            header.request_id.bytes
        )

        async with self._lock:
            target: asyncio.StreamWriter = writer if writer is not None else self.writer
            target.write(header_bytes + body_bytes)
            await target.drain()

        print("Send Response")

    async def run(self) -> None:
        Path(SOCKET_PATH).unlink(missing_ok=True)

        server = await asyncio.start_unix_server(
            self.handle_client,
            path=SOCKET_PATH,
        )

        self._owns_socket = True

        os.chmod(SOCKET_PATH, 0o660)

        async with server:
            await server.serve_forever()

    async def send(self, body_message: bytes, dtype: DataType, version: Version = Version.V1) -> None:
        header: Header = Header(
            version=version,
            type=dtype,
            body_length=len(body_message),
        )
        header_bytes: bytes = struct.pack(
            "!BBI",
            header.version,
            header.type,
            header.body_length,
        )

        async with self._lock:
            targets: tuple[asyncio.StreamWriter, ...] = tuple(self._runtime_writers)

            for writer in targets:
                if writer.is_closing():
                    continue

                try:
                    writer.write(header_bytes + body_message)
                    await writer.drain()
                except ConnectionError:
                    pass

    async def forward_command(self, body: bytes) -> bool:
        header: bytes = struct.pack("!BBI", Version.V1, DataType.COMMAND, len(body))
        delivered: bool = False

        async with self._lock:
            targets: tuple[asyncio.StreamWriter, ...] = tuple(self._runtime_writers)

            for writer in targets:
                if writer.is_closing():
                    continue

                try:
                    writer.write(header + body)
                    await writer.drain()
                    delivered = True
                except ConnectionError:
                    pass

        return delivered

    def start(self) -> None:
        if self._worker is not None:
            return

        self._worker = asyncio.create_task(self.run())

    async def close(self) -> None:
        worker: asyncio.Task[None] | None = self._worker
        self._worker = None

        if worker is not None:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)

        clients: list[asyncio.Task[None]] = list(self._clients)

        for writer in self._writers:
            writer.close()

        for task in clients:
            task.cancel()

        await asyncio.gather(*clients, return_exceptions=True)

        self._reader = None
        self._writer = None

        if self._owns_socket:
            Path(SOCKET_PATH).unlink(missing_ok=True)
            self._owns_socket = False

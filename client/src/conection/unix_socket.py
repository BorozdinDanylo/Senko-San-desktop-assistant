from senko_protocol.model import Response, Header, ResponseBody
from senko_protocol.enum import Version, DataType
from senko_protocol.path import SOCKET_PATH
from senko_protocol.meta import SingletonMeta
from senko_protocol.typing import AudioArray
from components import Queues
from collections.abc import Callable, Coroutine
from functools import wraps
from uuid import uuid4
from typing import Any, Concatenate
import numpy as np
import struct
import asyncio


MAX_BODY_SIZE = 16 * 1024 * 1024


def catch_errors[**P, R](
        func: Callable[Concatenate["UnixSocket", P], Coroutine[Any, Any, R]],
) -> Callable[Concatenate["UnixSocket", P], Coroutine[Any, Any, R | Response]]:
    @wraps(func)
    async def wrapper(
            self: "UnixSocket",
            *args: P.args,
            **kwargs: P.kwargs,
    ) -> R | ResponseBody:
        try:
            return await func(self, *args, **kwargs)

        except (ConnectionError, BrokenPipeError, OSError, RuntimeError, ValueError) as error_message:
            await self.disconnect()
            await self.connect()

            return Response(
                header=Header(
                    version=Version.V1,
                    type=DataType.RESPONSE,
                    body_length=0,
                ),
                body=ResponseBody(
                    status_code=503,
                    message=error_message,
                ),
            )

    return wrapper


class UnixSocket(metaclass=SingletonMeta):
    def __init__(self):
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

        self._pending: dict[str, asyncio.Future[ResponseBody]] = {}
        self._listener: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def reader(self) -> asyncio.StreamReader:
        if self._reader is None:
            raise RuntimeError("Socket is not connected")

        return self._reader

    @property
    def writer(self) -> asyncio.StreamWriter:
        if self._writer is None:
            raise RuntimeError("Socket is not connected")

        return self._writer

    async def connect(self):
        print("Connecting")
        if self._reader is None or self._writer is None:
            self._reader, self._writer = await asyncio.open_unix_connection(
                str(SOCKET_PATH),
            )

    async def disconnect(self):
        try:
            if self.writer is not None:
                self.writer.close()
                await self.writer.wait_closed()
        finally:
            self._reader = None
            self._writer = None

    @catch_errors
    async def listen(self):
        try:
            while True:
                version_code, = await self.reader.readexactly(1)
                try:
                    print(version_code)
                    version = Version(version_code)
                except ValueError:
                    raise RuntimeError("Version is unknown")

                message_type: DataType
                body_length: int
                request_id: str = ""

                match version:
                    case Version.V1:
                        header_data = await self.reader.readexactly(5)
                        message_type, body_length = struct.unpack("!BI", header_data)
                    case Version.V2:
                        header_data = await self.reader.readexactly(21)
                        message_type, body_length, request_id = struct.unpack("!BI16s", header_data)

                data: bytes = await self.reader.readexactly(body_length)

                match message_type:
                    case DataType.RESPONSE:
                        future = self._pending.get(request_id)
                        if future is not None:
                            response: ResponseBody = ResponseBody.model_validate_json(data)
                            future.set_result(response)

                    case DataType.AUDIO:
                        print("Got audio data")
                        await Queues.audio_queue.put(data)

        except asyncio.CancelledError:
            pass

    async def send(self, data: bytes, dtype: DataType, request_id: str = ""):
        header = Header(
            version=Version.V2,
            type=dtype,
            body_length=len(data),
            request_id=request_id,
        )

        header_bytes = struct.pack(
            "!BBI16s",
            header.version,
            header.type,
            header.body_length,
            header.request_id.encode(),
        )

        async with self._lock:
            self.writer.write(header_bytes + data)
            await self.writer.drain()

    async def fetch(self, data: bytes, dtype: DataType):
        request_id = str(uuid4())

        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future

        try:
            await self.send(data, dtype, request_id)
            response: ResponseBody = await asyncio.wait_for(future, timeout=10)
        finally:
            self._pending.pop(request_id, None)

        print(f"Response staus is {response.status_code} and message is {response.message}")





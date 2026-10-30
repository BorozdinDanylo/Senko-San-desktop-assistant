from senko_protocol.model import Response, Request, Header, ResponseBody
from senko_protocol.enum import Version, DataType
from collections.abc import Callable, Coroutine
from pathlib import Path
from functools import wraps
from typing import Any, Concatenate, Self, Literal
import struct
import asyncio


SOCKET_PATH = Path("/run/senko/senko.sock")
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


class UnixSocket:
    singleton: Self | None = None

    def __new__(cls):
        if cls.singleton is None:
            obj = super().__new__(cls)
            cls.singleton = obj
            return obj

        return cls.singleton

    def __init__(self):
        if not SOCKET_PATH.exists():
            raise FileNotFoundError("Socket does not exist")

        if getattr(self, "initialized", False):
            return

        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

        self.initialized: Literal[True] = True

    async def connect(self):
        self.reader, self.writer = await asyncio.open_unix_connection(
            str(SOCKET_PATH),
        )

    async def disconnect(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

    @catch_errors
    async def send_message(self, message: Request) -> Response:
        if self.writer is None or self.reader is None:
            raise RuntimeError("Socket is not connected")

        body: bytes = message.body

        header = struct.pack(
            "!BBI",
            message.header.version,
            message.header.type,
            len(body),
        )

        self.writer.write(header + body)
        await self.writer.drain()

        version_code, = await self.reader.readexactly(1)
        version = Version(version_code)
        if version != Version.V1:
            raise RuntimeError("Version is unknown")

        header_data = await self.reader.readexactly(5)
        message_type, body_length = struct.unpack("!BI", header_data)

        if body_length > 16 * 1024 * 1024:
            raise ValueError("Response too large")

        if DataType(message_type) != DataType.RESPONSE:
            raise ValueError("Response is not a response")

        response_body = await self.reader.readexactly(body_length)

        return Response(
            header=Header(
                version=version,
                type=message_type,
                body_length=body_length,
            ),
            body=ResponseBody.model_validate_json(response_body),
        )


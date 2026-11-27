from senko_protocol.model import Response, Header, ResponseBody
from senko_protocol.enum import Version, DataType
from senko_protocol.path import SOCKET_PATH
from senko_protocol.meta import SingletonMeta
from senko_client.components import Queues
import logging
import uuid
import struct
import asyncio


RECONNECT_DELAY: float = 5.0
logger: logging.Logger = logging.getLogger(__name__)


MAX_BODY_SIZE: int = 16 * 1024 * 1024


class UnixSocket(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

        self._pending: dict[uuid.UUID, asyncio.Future[ResponseBody]] = {}
        self._listener: asyncio.Task[None] | None = None
        self._lock: asyncio.Lock = asyncio.Lock()

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

    async def connect(self) -> None:
        if self._listener is None or self._listener.done():
            self._listener = asyncio.create_task(self._maintain_connection())

    async def _maintain_connection(self) -> None:
        while True:
            try:
                self._reader, self._writer = await asyncio.open_unix_connection(
                    str(SOCKET_PATH),
                )
                await self.listen()

            except (OSError, EOFError, ValueError, RuntimeError) as error:
                logger.warning("Socket disconnected: %s; retrying in 5 seconds", error)

            finally:
                await self._close_connection()

            await asyncio.sleep(RECONNECT_DELAY)

    async def _close_connection(self) -> None:
        writer: asyncio.StreamWriter | None = self._writer
        self._reader = None
        self._writer = None

        for future in self._pending.values():
            if not future.done():
                future.set_result(ResponseBody(status_code=503, message="Socket disconnected"))

        if writer is not None:
            writer.close()

            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def disconnect(self) -> None:
        listener: asyncio.Task[None] | None = self._listener
        self._listener = None

        if listener is not None:
            listener.cancel()
            await asyncio.gather(listener, return_exceptions=True)

        await self._close_connection()

    async def listen(self) -> None:
        try:
            while True:
                version_code, = await self.reader.readexactly(1)
                try:
                    print(f"{version_code=}")
                    version: Version = Version(version_code)
                except ValueError:
                    raise RuntimeError("Version is unknown")

                message_type: DataType
                body_length: int
                request_id: uuid.UUID | None = None

                match version:
                    case Version.V1:
                        header_data: bytes = await self.reader.readexactly(5)
                        message_type, body_length = struct.unpack("!BI", header_data)
                    case Version.V2:
                        header_data = await self.reader.readexactly(21)
                        message_type, body_length, request_bytes = struct.unpack("!BI16s", header_data)
                        request_id = uuid.UUID(bytes=request_bytes)
                        print(f"Got {request_id=}")

                if body_length > MAX_BODY_SIZE:
                    raise ValueError("Socket message too large")

                data: bytes = await self.reader.readexactly(body_length)

                match message_type:
                    case DataType.RESPONSE:
                        assert request_id is not None
                        future: asyncio.Future[ResponseBody] | None = self._pending.get(request_id)
                        if future is not None and not future.done():
                            response: ResponseBody = ResponseBody.model_validate_json(data)
                            future.set_result(response)

                    case DataType.AUDIO:
                        print("Got audio data")
                        await Queues.audio_queue.put(data)

        except asyncio.CancelledError:
            raise

    async def send(self, data: bytes, dtype: DataType, request_id: uuid.UUID) -> None:
        header: Header = Header(
            version=Version.V2,
            type=dtype,
            body_length=len(data),
            request_id=request_id,
        )
        assert header.request_id is not None
        header_bytes: bytes = struct.pack(
            "!BBI16s",
            header.version,
            header.type,
            header.body_length,
            header.request_id.bytes,
        )

        async with self._lock:
            self.writer.write(header_bytes + data)
            await self.writer.drain()

    async def fetch(self, data: bytes, dtype: DataType) -> Response:
        request_id: uuid.UUID = uuid.uuid4()
        print(f"Sending {request_id=}...")

        future: asyncio.Future[ResponseBody] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future

        try:
            await self.send(data, dtype, request_id)
            response: ResponseBody = await asyncio.wait_for(future, timeout=10)

        except (OSError, RuntimeError, TimeoutError) as error:
            response = ResponseBody(status_code=503, message=str(error))

        finally:
            self._pending.pop(request_id, None)

        print(f"Response staus is {response.status_code} and message is {response.message}")
        return Response(
            header=Header(
                version=Version.V2,
                type=dtype,
                body_length=len(data),
                request_id=request_id,
            ),
            body=response,
        )

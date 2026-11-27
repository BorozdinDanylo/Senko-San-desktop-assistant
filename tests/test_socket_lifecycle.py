from collections.abc import Callable
from unittest.mock import _patch
import asyncio
from pathlib import Path
import signal
import struct
import uuid
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from conection.unix_socket import UnixSocket as ClientSocket
from senko_client.components import Queues
from senko_protocol.enum import DataType, Version, Commands, MicrophoneActions
from senko_protocol.model import Response, ResponseBody
from senko_protocol.lifecycle import run_until_stopped
from senko_protocol.meta import SingletonMeta
from server.transport.unix import UnixSocket as ServerSocket


class SocketLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.path: Path = Path(self.directory.name) / "senko.sock"
        self.patches: list[_patch] = [
            patch("conection.unix_socket.SOCKET_PATH", self.path),
            patch("conection.unix_socket.RECONNECT_DELAY", 0.02),
            patch("server.transport.unix.SOCKET_PATH", self.path),
        ]

        for replacement in self.patches:
            replacement.start()

        SingletonMeta._instances.pop(ClientSocket, None)
        SingletonMeta._instances.pop(ServerSocket, None)
        self.client: ClientSocket = ClientSocket()
        self.server: ServerSocket = ServerSocket()

    async def asyncTearDown(self) -> None:
        await self.client.disconnect()
        await self.server.close()

        for replacement in reversed(self.patches):
            replacement.stop()

        SingletonMeta._instances.pop(ClientSocket, None)
        SingletonMeta._instances.pop(ServerSocket, None)
        self.directory.cleanup()

    async def wait_connected(self) -> None:
        async with asyncio.timeout(2):
            while self.client._writer is None or self.server._writer is None:
                await asyncio.sleep(0.005)

    async def test_reconnect_after_missing_server_and_disconnect(self) -> None:
        await self.client.connect()
        await asyncio.sleep(0.04)
        self.assertIsNone(self.client._writer)

        self.server.start()
        await self.wait_connected()
        previous_writer: asyncio.StreamWriter = self.client.writer

        await self.server.close()
        self.assertFalse(self.path.exists())
        self.assertFalse(self.server._clients)

        self.server.start()

        async with asyncio.timeout(2):
            while self.client._writer is previous_writer:
                await asyncio.sleep(0.005)

        await self.wait_connected()
        self.assertIsNot(self.client.writer, previous_writer)

    async def test_disconnect_stops_retrying(self) -> None:
        await self.client.connect()
        await asyncio.sleep(0.01)
        await self.client.disconnect()
        await self.client.disconnect()

        self.server.start()
        await asyncio.sleep(0.06)
        self.assertIsNone(self.client._writer)
        self.assertIsNone(self.client._listener)

    async def test_server_closes_active_connection(self) -> None:
        self.server.start()

        async with asyncio.timeout(2):
            while not self.path.exists():
                await asyncio.sleep(0.005)

        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter
        reader, writer = await asyncio.open_unix_connection(str(self.path))
        await asyncio.sleep(0.01)
        await self.server.close()

        self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
        self.assertFalse(self.path.exists())
        self.assertFalse(self.server._clients)
        writer.close()
        await writer.wait_closed()

    async def test_requests_work_after_reconnect(self) -> None:
        await self.client.connect()
        self.server.start()
        await self.wait_connected()

        with patch("server.transport.unix.Events.on_audio_receiving.emit", new_callable=AsyncMock):
            response: Response = await self.client.fetch(b"\x00" * 4, DataType.AUDIO)
            self.assertEqual(response.body.status_code, 200)

            await self.server.close()
            self.server.start()
            await asyncio.sleep(0.04)
            await self.wait_connected()

            response = await self.client.fetch(b"\x00" * 4, DataType.AUDIO)
            self.assertEqual(response.body.status_code, 200)

    async def test_disconnection_resolves_pending_request(self) -> None:
        await self.client.connect()
        self.server.start()
        await self.wait_connected()

        with patch.object(self.server, "response", new_callable=AsyncMock), patch(
            "server.transport.unix.Events.on_audio_receiving.emit", new_callable=AsyncMock,
        ):
            request: asyncio.Task[Response] = asyncio.create_task(
                self.client.fetch(b"\x00" * 4, DataType.AUDIO),
            )

            async with asyncio.timeout(2):
                while not self.client._pending:
                    await asyncio.sleep(0.005)

            await self.server.close()
            response: Response = await asyncio.wait_for(request, 1)

        self.assertEqual(response.body.status_code, 503)
        self.assertFalse(self.client._pending)

    async def test_offline_request_returns_unavailable(self) -> None:
        response: Response = await self.client.fetch(b"\x00" * 4, DataType.AUDIO)

        self.assertEqual(response.body.status_code, 503)
        self.assertFalse(self.client._pending)

    async def test_cli_commands_reach_registered_client_and_reply_to_cli(self) -> None:
        await self.client.connect(receive_commands=True)
        self.server.start()
        await self.wait_connected()

        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter
        reader, writer = await asyncio.open_unix_connection(str(self.path))

        try:
            for action in MicrophoneActions:
                body: bytes = struct.pack("!BB", Commands.MICROPHONE, action)
                request_id: uuid.UUID = uuid.uuid4()
                writer.write(struct.pack("!BBI16s", Version.V2, DataType.COMMAND, len(body), request_id.bytes) + body)
                await writer.drain()

                header: bytes = await asyncio.wait_for(reader.readexactly(22), 2)
                version: int
                dtype: int
                length: int
                response_id: bytes
                version, dtype, length, response_id = struct.unpack("!BBI16s", header)
                response: ResponseBody = ResponseBody.model_validate_json(await reader.readexactly(length))

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_id, request_id.bytes)
                self.assertEqual(dtype, DataType.RESPONSE)
                self.assertEqual(
                    await asyncio.wait_for(Queues.command_queue.get(), 2),
                    (Commands.MICROPHONE, action),
                )
                Queues.command_queue.task_done()
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_microphone_command_without_runtime_returns_unavailable(self) -> None:
        await self.client.connect()
        self.server.start()
        await self.wait_connected()

        response: Response = await self.client.fetch(
            struct.pack("!BB", Commands.MICROPHONE, MicrophoneActions.OFF),
            DataType.COMMAND,
        )

        self.assertEqual(response.body.status_code, 503)

    async def test_signals_wait_for_worker_cleanup(self) -> None:
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signum=signum):
                handlers: dict[signal.Signals, Callable[[], None]] = {}
                cleaned: asyncio.Event = asyncio.Event()
                loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

                async def worker() -> None:
                    try:
                        await asyncio.Event().wait()
                    finally:
                        await asyncio.sleep(0)
                        cleaned.set()

                with patch.object(loop, "add_signal_handler", side_effect=handlers.__setitem__), patch.object(loop, "remove_signal_handler"):
                    task: asyncio.Task[None] = asyncio.create_task(run_until_stopped(worker))
                    await asyncio.sleep(0)
                    handlers[signum]()
                    await asyncio.wait_for(task, 1)

                self.assertTrue(cleaned.is_set())

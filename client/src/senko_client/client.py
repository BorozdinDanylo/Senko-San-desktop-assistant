import asyncio
import logging

from audio import Microphone
from audio.output import Player
from senko_client.components.queue import Queues
from senko_client.unix_socket_client import SenkoClient
from senko_protocol.enum import Commands, MicrophoneActions


class Client:
    def __init__(self) -> None:
        self.microphone: Microphone = Microphone()
        self.player: Player = Player()

        self.senko: SenkoClient = SenkoClient()
        self._command_task: asyncio.Task[None] | None = None


    async def start(self) -> None:
        self._command_task = asyncio.create_task(self.command_handler())
        await self.microphone.start_streaming()
        await self.senko.start()
        self.player.start()

    async def command_handler(self) -> None:
        while True:
            command_code: int
            action_code: int
            command_code, action_code = await Queues.command_queue.get()

            try:
                command: Commands = Commands(command_code)

                match command:
                    case Commands.MICROPHONE:
                        action: MicrophoneActions = MicrophoneActions(action_code)
                        await self.microphone.set_status(action)

            except ValueError:
                logging.getLogger(__name__).warning(
                    "Invalid command: %s, action: %s", command_code, action_code,
                )
            finally:
                Queues.command_queue.task_done()

    async def stop(self) -> None:
        if self._command_task is not None:
            self._command_task.cancel()
            await asyncio.gather(self._command_task, return_exceptions=True)
            self._command_task = None

        try:
            await self.microphone.stop_streaming()
        finally:
            try:
                await self.senko.stop()
            finally:
                await self.player.stop()




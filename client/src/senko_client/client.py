from audio import Microphone
from audio.output import Player
from senko_client.unix_socket_client import SenkoClient


class Client:
    def __init__(self) -> None:
        self.microphone: Microphone = Microphone()
        self.player: Player = Player()

        self.senko: SenkoClient = SenkoClient()


    async def start(self) -> None:
        await self.microphone.start_streaming()
        await self.senko.start()
        self.player.start()

    async def stop(self) -> None:
        try:
            await self.microphone.stop_streaming()
        finally:
            try:
                await self.senko.stop()
            finally:
                await self.player.stop()




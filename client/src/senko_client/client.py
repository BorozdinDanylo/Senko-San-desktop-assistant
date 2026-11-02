from audio import Microphone
from audio.output import Player
from senko_client.unix_socket_client import SenkoClient


class Client:
    def __init__(self):
        self.microphone = Microphone()
        self.player = Player()

        self.senko = SenkoClient()


    async def start(self):
        await self.microphone.start_streaming()
        await self.senko.start()
        self.player.start()

    async def stop(self):
        await self.microphone.stop_streaming()
        await self.senko.stop()
        await self.player.stop()




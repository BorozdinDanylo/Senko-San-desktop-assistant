from audio import Microphone
from senko_client.unix_socket_client import SenkoClient


class Client:
    def __init__(self):
        self.microphone = Microphone()
        self.senko = SenkoClient()


    async def start(self):
        await self.microphone.start_streaming()
        await self.senko.start()

    async def stop(self):
        await self.microphone.stop_streaming()
        await self.senko.stop()




from audio import Microphone


class Client:
    def __init__(self):
        self.microphone = Microphone()


    async def start(self):
        await self.microphone.start_streaming()

    async def stop(self):
        await self.microphone.stop_streaming()




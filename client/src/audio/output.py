from senko_protocol.meta import SingletonMeta
from senko_client.components import Queues
import soundfile as sf
import sounddevice as sd
import asyncio
import io


_lock = asyncio.Lock()


class Player(metaclass=SingletonMeta):
    def __init__(self):
        self.playing: asyncio.Task | None = None

    @staticmethod
    async def play_audio():
        while True:
            audio_data: bytes = await Queues.audio_queue.get()

            audio, samplerate = sf.read(
                io.BytesIO(audio_data),
                dtype="float32",
            )

            async with _lock:
                sd.play(audio, samplerate)
                sd.wait()
            
    @staticmethod
    def interrupt():
        try:
            while True:
                Queues.audio_queue.get_nowait()
                Queues.audio_queue.task_done()
        finally:
            sd.stop()

    def start(self):
        if self.playing is None:
            self.playing = asyncio.create_task(self.play_audio())

    async def stop(self):
        if self.playing is None:
            return

        self.playing.cancel()

        try:
            await self.playing
        except asyncio.CancelledError:
            self.playing = None

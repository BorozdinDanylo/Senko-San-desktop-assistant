from voice.model import SENKO_SAN_VOICE_ID, SENKO_SAN_API_KEY
from voice import clear_queue
from fishaudio import AsyncFishAudio
from fishaudio.utils import play
import asyncio


class SenkoVoice:
    def __init__(self, tts_queue: asyncio.Queue[str]):
        self.client = AsyncFishAudio(api_key=SENKO_SAN_API_KEY)
        self.tts_queue = tts_queue
        self.audio_queue = asyncio.Queue[bytes]()

    async def tts_worker(self):
        while True:
            text = await self.tts_queue.get()

            audio = await self.client.tts.convert(
                text=text,
                reference_id=SENKO_SAN_VOICE_ID,
                model="s2.1-pro-free",  # type: ignore[arg-type]
                format="mp3",
            )

            await self.audio_queue.put(audio)

    async def speak(self):
        while True:
            audio = await self.audio_queue.get()

            await asyncio.to_thread(play, audio)

    def stop_talking(self):
        clear_queue(self.tts_queue)
        clear_queue(self.audio_queue)





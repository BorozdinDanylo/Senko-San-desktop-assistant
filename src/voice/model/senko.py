from voice.model import SENKO_SAN_VOICE_ID, SENKO_SAN_API_KEY
from fishaudio import AsyncFishAudio
from fishaudio.utils import play
import asyncio


class SenkoVoice:
    def __init__(self, tts_queue: asyncio.Queue[str]):
        self.client = AsyncFishAudio(api_key=SENKO_SAN_API_KEY)
        self.tts_queue = tts_queue

    async def speek(self):
        while True:
            text = await self.tts_queue.get()

            audio = await self.client.tts.convert(
                text=text,
                reference_id=SENKO_SAN_VOICE_ID,
                model="s2.1-pro-free",  # type: ignore[arg-type]
                format="mp3",
            )

            await asyncio.to_thread(play, audio)





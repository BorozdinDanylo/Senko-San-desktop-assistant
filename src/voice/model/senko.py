from voice.model import SENKO_SAN_VOICE_ID, SENKO_SAN_API_KEY
from voice import clear_queue
from pipeline import stop_talking_event
from ..model import AudioDict
from senko import NewMessage
from fishaudio import AsyncFishAudio
from fishaudio.utils import play
import asyncio


class SenkoVoice:
    def __init__(self, tts_queue: asyncio.Queue[str]):
        self.client: AsyncFishAudio = AsyncFishAudio(api_key=SENKO_SAN_API_KEY)
        self.tts_queue: asyncio.Queue[str] = tts_queue
        self.audio_queue: asyncio.Queue[AudioDict] = asyncio.Queue[AudioDict]()

        asyncio.create_task(self.stop_talking())

    async def tts_worker(self):
        while True:
            text = await self.tts_queue.get()

            audio = await self.client.tts.convert(
                text=text,
                reference_id=SENKO_SAN_VOICE_ID,
                model="s2.1-pro-free",  # type: ignore[arg-type]
                format="mp3",
            )

            NewMessage.add_text(text)

            await self.audio_queue.put(AudioDict(
                text=text,
                audio=audio,
            ))

    async def speak(self):
        while True:
            audio: AudioDict = await self.audio_queue.get()

            await asyncio.to_thread(play, audio["audio"])

            NewMessage.spoken(audio["text"])

    async def stop_talking(self):
        while True:
            await stop_talking_event.wait()

            clear_queue(self.tts_queue)
            clear_queue(self.audio_queue)

            stop_talking_event.clear()





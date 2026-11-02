from voice.model import SENKO_SAN_VOICE_ID, SENKO_SAN_API_KEY
from voice import clear_queue
from pipeline.components import Queues, Events
from ..model import AudioDict
from senko import NewMessage
from fishaudio.client import AsyncFishAudio
import asyncio


class SenkoVoice:
    def __init__(self):
        self.client: AsyncFishAudio = AsyncFishAudio(api_key=SENKO_SAN_API_KEY)
        self.audio_queue: asyncio.Queue[AudioDict] = asyncio.Queue[AudioDict]()

        Events.on_interrupt.subscribe(self.stop_talking)

    async def tts_worker(self):
        while True:
            text = await Queues.tts_queue.get()

            generation = NewMessage.generation
            audio = await self.client.tts.convert(
                text=text,
                reference_id=SENKO_SAN_VOICE_ID,
                model="s2.1-pro-free",  # type: ignore[arg-type]
                format="wav",
            )

            if generation != NewMessage.generation:
                continue

            await self.audio_queue.put(AudioDict(
                text=text,
                audio=audio,
                generation=generation,
            ))

    async def speak(self):
        while True:
            audio: AudioDict = await self.audio_queue.get()

            await Events.on_give_audio.emit(audio["audio"])

            if audio["generation"] == NewMessage.generation:
                NewMessage.spoken(audio["text"])

    async def stop_talking(self):
        clear_queue(Queues.tts_queue)
        clear_queue(self.audio_queue)





from pipeline.components.queues import Queues
from faster_whisper import WhisperModel
import numpy as np
import asyncio


class SpeechToText:
    def __init__(self):
        self.model = WhisperModel(
            "large-v3",
            device="cuda",
            compute_type="float16",
            local_files_only=True,
        )

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            audio,
            language="uk",
            vad_filter=True,
        )

        return " ".join(
            segment.text.strip()
            for segment in segments
        ).strip()

    async def worker(self):
        while True:
            audio = await Queues.audio_queue.get()

            text = await asyncio.to_thread(
                self.transcribe,
                audio,
            )


            if text:
                print(text)
                await Queues.transcription_queue.put(text)

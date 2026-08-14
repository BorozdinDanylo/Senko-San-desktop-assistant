from faster_whisper import WhisperModel
import numpy as np
import asyncio


class SpeechToText:
    def __init__(self, audio_queue: asyncio.Queue[np.ndarray], transcription_queue: asyncio.Queue[str]):
        self.audio_queue = audio_queue
        self.transcription_queue = transcription_queue

        self.model = WhisperModel(
            "small",
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
            audio = await self.audio_queue.get()

            text = await asyncio.to_thread(
                self.transcribe,
                audio,
            )


            if text:
                await self.transcription_queue.put(text)

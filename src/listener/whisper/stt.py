from listener.whisper import record
from faster_whisper import WhisperModel
import numpy as np
import asyncio


class SpeechToText:
    def __init__(self):
        print("Loading model...")
        self.model = WhisperModel(
            "small",
            device="cuda",
            compute_type="float16",
            local_files_only=True,
        )
        print("Model loaded.")

    def _transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            audio,
            language="uk",
            vad_filter=True,
        )

        return " ".join(
            segment.text.strip()
            for segment in segments
        ).strip()

    async def listen(self, duration: float = 5.0) -> str:
        audio = await asyncio.to_thread(
            record,
            duration,
        )

        text = await asyncio.to_thread(
            self._transcribe,
            audio,
        )

        return text


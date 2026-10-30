from components import Queues
from time import monotonic
from typing import Self, Literal
import sounddevice as sd
import numpy as np
import asyncio


SAMPLE_RATE = 16_000
MAX_SILENT_LENGTH = .8
MIN_SPEECH_CHUNKS_LENGTH = 30
MIN_VOLUME = -35


def is_speaking(audio: np.ndarray) -> bool:
    rms = np.sqrt(np.mean(audio.astype(np.float64) ** 2))
    db = 20 * np.log10(max(rms, 1e-10))

    print(db > MIN_VOLUME)
    return db > MIN_VOLUME


class Microphone:
    singleton: Self | None = None

    def __new__(cls, *args, **kwargs):
        if cls.singleton is None:
            obj = object.__new__(cls)
            cls.singleton = obj
            return obj

        return cls.singleton

    def __init__(self):
        if getattr(self, "initialized", False):
            return

        self.start_silent_at: float = monotonic()
        self.stream: asyncio.Task[None] | None = None
        self.sound_buffer: list[np.ndarray] = []
        self.loop = asyncio.get_running_loop()

        self.initialized: Literal[True] = True

    def sound_buffer_control(self, indata: np.ndarray, *_):
        audio_data: np.ndarray = indata[:, 0].copy()
        self.silent_check(audio_data)
        self.sound_buffer.append(audio_data)


    async def create_stream(self):
        with sd.InputStream(
                device="pipewire",
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=self.sound_buffer_control,
                blocksize=1600,  # приблизно 100 ms
        ):
            await asyncio.Event().wait()

    def silent_check(self, audio: np.ndarray):
        time_now: float = monotonic()

        if is_speaking(audio):
            self.start_silent_at = time_now

        if (self.start_silent_at + MAX_SILENT_LENGTH < time_now
                and self.sound_buffer
                and len(self.sound_buffer) > MIN_SPEECH_CHUNKS_LENGTH
        ):
            print("Silent Detected")
            print(len(self.sound_buffer))
            self.loop.call_soon_threadsafe(Queues.audio_queue.put_nowait, np.concatenate(self.sound_buffer))
            self.sound_buffer.clear()


    async def start_streaming(self):
        print("Start Streaming...")
        self.stream: asyncio.Task[None] = asyncio.create_task(self.create_stream())
        print("Stream Started")

    async def stop_streaming(self):
        if self.stream is None:
            return

        self.stream.cancel()

        try:
            await self.stream
        except asyncio.CancelledError:
            pass


__all__ = ["Microphone"]



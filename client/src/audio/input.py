from senko_client.components import Events
from senko_protocol.enum import MicrophoneActions
from time import monotonic
from typing import Self, Literal
import sounddevice as sd
import numpy as np
import asyncio


SAMPLE_RATE = 16_000
MAX_SILENT_LENGTH = .8
MIN_SPEECH_CHUNKS_LENGTH = 12
MIN_VOLUME = -35


def is_speaking(audio: np.ndarray) -> bool:
    rms = np.sqrt(np.mean(audio.astype(np.float64) ** 2))
    db = 20 * np.log10(max(rms, 1e-10))

    return db > MIN_VOLUME


class Microphone:
    singleton: Self | None = None

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        if cls.singleton is None:
            obj: Self = object.__new__(cls)
            cls.singleton = obj
            return obj

        return cls.singleton

    def __init__(self) -> None:
        if getattr(self, "initialized", False):
            return

        self.start_silent_at: float = monotonic()
        self.stream: asyncio.Task[None] | None = None
        self.sound_buffer: list[np.ndarray] = []
        self.loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        self._status: bool = False

        self.initialized: Literal[True] = True

    @property
    def status(self) -> bool:
        return self._status

    async def set_status(self, action: MicrophoneActions) -> None:
        enabled: bool = action == MicrophoneActions.ON

        if action == MicrophoneActions.SWITCH:
            enabled = not self._status

        if enabled:
            await self.start_streaming()
        else:
            await self.stop_streaming()

    def sound_buffer_control(self, indata: np.ndarray, *_: object) -> None:
        audio_data: np.ndarray = indata[:, 0].copy()
        self.silent_check(audio_data)
        self.sound_buffer.append(audio_data)


    async def create_stream(self) -> None:
        with sd.InputStream(
                device="pipewire",
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=self.sound_buffer_control,
                blocksize=1600,  # приблизно 100 ms
        ):
            await asyncio.Event().wait()

    def silent_check(self, audio: np.ndarray) -> None:
        time_now: float = monotonic()

        if is_speaking(audio):
            self.start_silent_at = time_now

        if (self.start_silent_at + MAX_SILENT_LENGTH < time_now
                and self.sound_buffer
                and len(self.sound_buffer) > MIN_SPEECH_CHUNKS_LENGTH
        ):
            print("Silent Detected")
            asyncio.run_coroutine_threadsafe(
                Events.on_audio_complete.emit(np.concatenate(self.sound_buffer)),
                self.loop,
            )
            self.sound_buffer.clear()
        elif not is_speaking(audio) and len(self.sound_buffer) < MIN_SPEECH_CHUNKS_LENGTH:
            self.sound_buffer.clear()


    async def start_streaming(self) -> None:
        if self.stream is not None and not self.stream.done():
            return

        self.start_silent_at = monotonic()
        print("Start Streaming...")
        self.stream = asyncio.create_task(self.create_stream())
        print("Stream Started")
        self._status = True

    async def stop_streaming(self) -> None:
        if self.stream is None:
            return

        self.stream.cancel()

        try:
            await self.stream
        except asyncio.CancelledError:
            pass
        finally:
            self.stream = None
            self.sound_buffer.clear()
            self._status = False


__all__ = ["Microphone"]



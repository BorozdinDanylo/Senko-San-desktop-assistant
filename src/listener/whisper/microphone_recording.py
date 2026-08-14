from listener.config import SAMPLE_RATE, CHUNK_SAMPLES, STEP_SAMPLES
import sounddevice as sd
import numpy as np
import asyncio


async def microphone(audio_queue: asyncio.Queue[np.ndarray]):
    loop = asyncio.get_running_loop()

    buffer = np.empty(0, dtype=np.float32)

    def callback(indata, frames, time, status):
        nonlocal buffer

        if status:
            print(status)

        data = indata[:, 0].copy()
        buffer = np.concatenate((buffer, data))

        while len(buffer) >= CHUNK_SAMPLES:
            chunk = buffer[:CHUNK_SAMPLES].copy()
            buffer = buffer[STEP_SAMPLES:]

            loop.call_soon_threadsafe(
                audio_queue.put_nowait,
                chunk,
            )

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=callback,
        blocksize=1600,  # приблизно 100 ms
    ):
        await asyncio.Event().wait()


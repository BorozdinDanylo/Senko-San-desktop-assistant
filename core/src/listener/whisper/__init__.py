import sounddevice as sd
import numpy as np


def record(duration: float = 5.0) -> np.ndarray:
    sample_rate = 16_000

    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
    )

    sd.wait()

    return audio.flatten()

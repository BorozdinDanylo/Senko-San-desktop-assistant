# /// script
# dependencies = [
#     "sounddevice",
#     "numpy",
# ]
# ///

import numpy as np
import sounddevice as sd

DURATION = 5
SAMPLE_RATE = 16000


def calculate_db(audio: np.ndarray) -> float:
    rms = np.sqrt(np.mean(audio.astype(np.float64) ** 2))
    return float(20 * np.log10(max(rms, 1e-10)))


def main():
    print(f"Recording for {DURATION} seconds...")

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )

    sd.wait()

    audio = audio.flatten()

    # Середня гучність усього запису
    average_db = calculate_db(audio)

    # Максимальна гучність серед блоків по 100 мс
    chunk_size = SAMPLE_RATE // 10

    chunk_volumes = [
        calculate_db(audio[i:i + chunk_size])
        for i in range(0, len(audio), chunk_size)
    ]

    maximum_db = max(chunk_volumes)

    print("\nResults:")
    print(f"Average volume: {average_db:.2f} dBFS")
    print(f"Maximum volume: {maximum_db:.2f} dBFS")
    print(f"Minimum volume: {min(chunk_volumes):.2f} dBFS")

    print("\nVolume by 100 ms chunks:")

    for i, volume in enumerate(chunk_volumes):
        print(f"{i / 10:4.1f}s: {volume:7.2f} dBFS")


if __name__ == "__main__":
    main()
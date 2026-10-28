import numpy as np
import asyncio


class Queues:
    audio_queue = asyncio.Queue[np.ndarray]()
    transcription_queue = asyncio.Queue[str]()
    text_queue = asyncio.Queue[str]()
    text_analiz = asyncio.Queue[str]()
    tts_queue = asyncio.Queue[str]()



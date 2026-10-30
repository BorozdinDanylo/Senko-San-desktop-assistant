import asyncio

import numpy as np


class Queues:
    audio_queue: asyncio.Queue[np.ndarray] = asyncio.Queue[np.ndarray]()

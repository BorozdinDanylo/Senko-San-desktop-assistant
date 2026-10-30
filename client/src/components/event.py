from senko_protocol.event import AsyncEvent
import numpy as np


class Events:
    on_audio_complete: AsyncEvent[[np.ndarray]] = AsyncEvent()

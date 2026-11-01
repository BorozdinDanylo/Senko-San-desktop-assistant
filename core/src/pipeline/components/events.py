from senko_protocol.event import AsyncEvent
from senko_protocol.typeing import AudioArray
import numpy as np


class Events:
    on_senko_answer: AsyncEvent[[str]] = AsyncEvent[[str]]()
    on_interrupt: AsyncEvent[[]] = AsyncEvent[[]]()
    on_audio_receiving: AsyncEvent[[AudioArray]] = AsyncEvent[[np.ndarray]]()






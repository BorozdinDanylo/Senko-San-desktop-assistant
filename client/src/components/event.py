from senko_protocol.event import AsyncEvent
from senko_protocol.typing import AudioArray


class Events:
    on_audio_complete: AsyncEvent[[AudioArray]] = AsyncEvent()
    on_get_audio: AsyncEvent[[AudioArray]] = AsyncEvent()

from .events import Events
from .queues import Queues
from senko_protocol.meta import SingletonMeta
from senko_protocol.typing import AudioArray
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from listener.whisper.stt import SpeechToText
    from senko.models.speaker import Speaker
    from voice.model.senko import SenkoVoice
    from server.server import Server


class Runtime(metaclass=SingletonMeta):
    def __init__(self) -> None:
        from listener.whisper.stt import SpeechToText
        from senko.models.speaker import Speaker
        from voice.model.senko import SenkoVoice
        from server.server import Server

        self.stt: SpeechToText = SpeechToText()
        self.senko: Speaker = Speaker()
        self.voice: SenkoVoice = SenkoVoice()

        self.server: Server = Server()
        self.server.start()


    async def close(self) -> None:
        async with AsyncExitStack() as resources:
            resources.push_async_callback(self.senko.history.close)
            resources.push_async_callback(self.senko.client.close)
            resources.push_async_callback(self.voice.client.close)
            resources.push_async_callback(self.server.close)


    @staticmethod
    @Events.on_audio_receiving
    async def audio_receiving(audio: AudioArray) -> None:
        await Queues.audio_queue.put(audio)






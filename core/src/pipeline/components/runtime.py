from .events import Events
from .queues import Queues
from senko_protocol.meta import SingletonMeta
from senko_protocol.typing import AudioArray
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from listener.whisper.stt import SpeechToText
    from senko.models.speaker import Speaker
    from voice.model.senko import SenkoVoice
    from server.server import Server


class Runtime(metaclass=SingletonMeta):
    def __init__(self):
        from listener.whisper.stt import SpeechToText
        from senko.models.speaker import Speaker
        from voice.model.senko import SenkoVoice
        from server.server import Server

        self.stt = SpeechToText()
        self.senko = Speaker()
        self.voice = SenkoVoice()

        self.server: Server = Server()
        self.server.start()


    @staticmethod
    @Events.on_audio_receiving
    async def audio_receiving(audio: AudioArray):
        await Queues.audio_queue.put(audio)






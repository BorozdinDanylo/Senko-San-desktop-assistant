from typing import TYPE_CHECKING, Self, Literal

if TYPE_CHECKING:
    from listener.text_combining.text_input import TextInput
    from listener.whisper.stt import SpeechToText
    from senko.models.speaker import Speaker
    from voice.model.senko import SenkoVoice


class Runtime:
    _singleton: Self | None = None

    def __new__(cls) -> Self:
        if cls._singleton is None:
            obj: Self = super().__new__(cls)
            cls._singleton = obj
            return obj

        return cls._singleton

    def __init__(self):
        if getattr(self, "initialized", False):
            return

        from listener.whisper.stt import SpeechToText
        from listener.text_combining.text_input import TextInput
        from senko.models.speaker import Speaker
        from voice.model.senko import SenkoVoice

        self.stt = SpeechToText()
        self.text_input = TextInput()
        self.senko = Speaker()
        self.voice = SenkoVoice()

        self.initialized: Literal[True] = True






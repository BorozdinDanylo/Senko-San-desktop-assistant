from .events_control import EventManager, add_answer_queue, stop_talking_event


def initialize():
    """Create runtime services at launch, not when importing shared events."""
    global audio_queue, transcription_queue, text_analiz, tts_queue
    global stt, text_input, senko, voice
    from listener.whisper.stt import SpeechToText
    from listener.text_combining.text_input import TextInput
    from senko.models.speaker import Speaker
    from voice.model.senko import SenkoVoice
    import asyncio

    audio_queue = asyncio.Queue()
    transcription_queue = asyncio.Queue()
    text_analiz = asyncio.Queue()
    tts_queue = asyncio.Queue()
    stt = SpeechToText(audio_queue, transcription_queue)
    text_input = TextInput(transcription_queue, text_analiz)
    senko = Speaker(text_analiz, tts_queue)
    voice = SenkoVoice(tts_queue)

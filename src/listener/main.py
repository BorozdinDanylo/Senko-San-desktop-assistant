from dotenv import load_dotenv
load_dotenv()

from listener.whisper.stt import SpeechToText
from listener.whisper.microphone_recording import microphone
from listener.text_combining.text_input import TextInput
from senko.models.speaker import Speaker
import asyncio


async def print_transcriptions(transcription_queue: asyncio.Queue[str]):
    while True:
        text = await transcription_queue.get()
        print("HEARD:", text)


async def worker():
    audio_queue = asyncio.Queue()
    transcription_queue = asyncio.Queue()
    text_analiz = asyncio.Queue()
    tts_queue = asyncio.Queue()

    stt = SpeechToText(audio_queue, transcription_queue)
    text_input = TextInput(transcription_queue, text_analiz)
    senko = Speaker(text_analiz, tts_queue)

    await asyncio.gather(
        microphone(audio_queue),
        stt.worker(),
        text_input.hear(),
        senko.live(),
    )


def main():
    asyncio.run(worker())


if __name__ == '__main__':
    main()


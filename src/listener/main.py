from dotenv import load_dotenv
load_dotenv()

from listener.whisper.stt import SpeechToText
import asyncio


audio_queue = asyncio.Queue()
transcription_queue = asyncio.Queue()
request_queue = asyncio.Queue()
tts_queue = asyncio.Queue()

stt = SpeechToText()


async def worker():
    print("Worker started")
    while True:
        print(await stt.listen())


def main():
    asyncio.run(worker())


if __name__ == '__main__':
    main()


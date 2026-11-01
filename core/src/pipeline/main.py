from dotenv import load_dotenv
load_dotenv()

from .components import Runtime, Queues
from server import Server
from listener.whisper.microphone_recording import microphone
import asyncio


async def worker():
    runtime: Runtime = Runtime()

    server: Server = Server()
    server.start()

    await asyncio.gather(
        microphone(Queues.audio_queue),
        runtime.stt.worker(),
        runtime.text_input.hear(),
        runtime.senko.live(),
        runtime.voice.tts_worker(),
        runtime.voice.speak(),
    )


def main():
    asyncio.run(worker())


if __name__ == '__main__':
    main()


from dotenv import load_dotenv
load_dotenv()

from pipeline.components import Runtime, Queues
from server import Server
import asyncio


async def worker():
    runtime: Runtime = Runtime()

    server: Server = Server()
    server.start()

    await asyncio.gather(
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


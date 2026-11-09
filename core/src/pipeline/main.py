from dotenv import load_dotenv
load_dotenv()

from core.components import Runtime
from tools import CodexTool
import asyncio


async def worker():
    runtime: Runtime = Runtime()

    try:
        await asyncio.gather(
            runtime.stt.worker(),
            runtime.senko.live(),
            runtime.voice.tts_worker(),
            runtime.voice.speak(),
        )
    finally:
        try:
            await CodexTool.shutdown()
        finally:
            await runtime.server.close()


def main():
    asyncio.run(worker())


if __name__ == '__main__':
    main()


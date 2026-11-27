from dotenv import load_dotenv
load_dotenv()

from core.components import Runtime
from tools import CodexTool
from senko_protocol.lifecycle import run_until_stopped
import asyncio


async def worker() -> None:
    runtime: Runtime = Runtime()

    try:
        async with asyncio.TaskGroup() as workers:
            workers.create_task(runtime.stt.worker())
            workers.create_task(runtime.senko.live())
            workers.create_task(runtime.voice.tts_worker())
            workers.create_task(runtime.voice.speak())

    finally:
        try:
            await CodexTool.shutdown()
        finally:
            await runtime.close()


def main() -> None:
    asyncio.run(run_until_stopped(worker))


if __name__ == '__main__':
    main()

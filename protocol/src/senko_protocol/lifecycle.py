from collections.abc import Callable, Coroutine
from typing import Any
import asyncio
import signal


async def run_until_stopped(worker: Callable[[], Coroutine[Any, Any, None]]) -> None:
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    stop: asyncio.Event = asyncio.Event()
    signals: tuple[signal.Signals, ...] = (signal.SIGINT, signal.SIGTERM)

    for signum in signals:
        loop.add_signal_handler(signum, stop.set)

    task: asyncio.Task[None] = asyncio.create_task(worker())
    stopping: asyncio.Task[bool] = asyncio.create_task(stop.wait())

    try:
        await asyncio.wait((task, stopping), return_when=asyncio.FIRST_COMPLETED)

        if task.done():
            await task

    finally:
        task.cancel()
        stopping.cancel()

        try:
            await asyncio.gather(task, stopping, return_exceptions=True)

            if not task.cancelled():
                task.result()
        finally:
            for signum in signals:
                loop.remove_signal_handler(signum)

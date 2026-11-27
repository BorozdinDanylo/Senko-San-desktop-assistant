import asyncio


class Queues:
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue[bytes]()
    command_queue: asyncio.Queue[tuple[int, int]] = asyncio.Queue[tuple[int, int]]()

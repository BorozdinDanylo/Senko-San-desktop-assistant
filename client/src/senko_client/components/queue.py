import asyncio


class Queues:
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue[bytes]()

import asyncio

add_answer_queue: asyncio.Queue[str] = asyncio.Queue[str]()

import asyncio


def clear_queue(queue: asyncio.Queue):
    while True:
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            break
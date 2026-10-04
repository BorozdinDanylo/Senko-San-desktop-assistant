from .events import stop_talking_event
from .queues import add_answer_queue


class EventManager:
    @staticmethod
    async def add_answer(answer: str):
        await add_answer_queue.put(answer)

    @staticmethod
    def stop_talking():
        stop_talking_event.set()

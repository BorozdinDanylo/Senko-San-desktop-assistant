from senko_protocol.event import AsyncEvent


class Events:
    on_senko_answer: AsyncEvent[[str]] = AsyncEvent[[str]]()
    on_interrupt: AsyncEvent[[]] = AsyncEvent[[]]()






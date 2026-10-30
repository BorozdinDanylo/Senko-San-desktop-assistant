from collections.abc import Callable, Awaitable
from typing import Self
import asyncio


class AsyncEvent[**P]:
    def __init__(self):
        self._handles: list[Callable[P, Awaitable[None]]] = []

    def subscribe(self, func: Callable[P, Awaitable[None]]) -> Self:
        self._handles.append(func)
        return self

    def unsubscribe(self, func: Callable[P, Awaitable[None]]):
        self._handles.remove(func)

    async def emit(self, *args: P.args, **kwargs: P.kwargs):
        coroutines: list[Awaitable[None]] = [
            handles(*args, **kwargs)
            for handles in self._handles
        ]
        await asyncio.gather(*coroutines)

    def __call__(
        self,
        func: Callable[P, Awaitable[None]]
    ) -> Callable[P, Awaitable[None]]:
        self.subscribe(func)
        return func




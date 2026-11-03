from openai.types.responses import ResponseInputParam, ResponseInputItemParam
from typing import overload
import tiktoken


MAX_TOKEN_SIZE = 1_000


def get_text_from_history_part(history_part: list[ResponseInputParam]) -> str:
    text = "\n".join(
        message["content"]
        for group in history_part
        for message in group
        if isinstance(message.get("content"), str)
    )

    return text


class History:
    def __init__(self):
        self._history: list[ResponseInputParam] = []
        self._encoding = tiktoken.encoding_for_model("gpt-5.6-luna")

    def create_first_chunk(self): ...

    def add(self, message: ResponseInputItemParam):
        self._history[-1].append(message)

    def open_new_chunk(self):
        if self.size() > MAX_TOKEN_SIZE:
            self.compressing()

        self._history.append([])

    @overload
    def size(self) -> int: ...

    @overload
    def size(self, start: int, end: int) -> int: ...

    def size(self, start: int | None = None, end: int | None = None) -> int:
        if start is None and end is None:
            text: str = get_text_from_history_part(self._history)

        elif start is not None and end is not None:
            start = 0 if start < 0 else start
            start = len(self._history) - 1 if start >= len(self._history) else start

            end = 0 if end < 0 else end
            end = len(self._history) - 1 if end >= len(self._history) else end

            text: str = get_text_from_history_part(self._history[start:end])

        else:
            raise ValueError("Offset and limit are mutually exclusive")

        history_tokens: list[int] = self._encoding.encode(text)

        print(f"Token size is: {len(history_tokens)}")
        return len(history_tokens)

    def get(self) -> list[ResponseInputParam]:
        return self._history

    def compressing(self):
        compressed: list[ResponseInputParam] = []
        while self.size() >= MAX_TOKEN_SIZE:
            compressed.append(self._history[2])
            self._history.pop(2)

        print(f"Compressed {len(compressed)} chunks")







from components.path import SYSTEM_SENKO_PROMPT
from openai.types.responses import ResponseInputParam, EasyInputMessageParam, ResponseInputItemParam
from openai import AsyncOpenAI
from openai.types.shared_params import Reasoning, ResponsesModel
from openai.types.responses import Response
from typing import overload
from pathlib import Path
import tiktoken
import json


MAX_TOKEN_SIZE = 240_000
COMPRESS_TO_SIZE = 130_000

MAIN_MEMORIES_PATH = Path("/home/Senka/main_memories.md")
NOTES_TO_NEXT_START_PATH = Path("/home/Senka/notes_to_next_start.md")

SUMMARY_MODEL: ResponsesModel = "gpt-5.6-luna"
SUMMARY_REASONING: Reasoning = Reasoning(
    effort="none",
)


def get_text_from_history_part(history_part: list[ResponseInputParam]) -> str:
    return json.dumps(history_part, ensure_ascii=False)


class History:
    def __init__(self):
        self._history: list[ResponseInputParam] = []
        self._encoding = tiktoken.encoding_for_model("gpt-5.6-luna")

        self.summary_client: AsyncOpenAI = AsyncOpenAI()

    @staticmethod
    def create_first_chunk(is_program_starting: bool = False) -> ResponseInputParam:
        first_chunk: list[ResponseInputItemParam] = [
            EasyInputMessageParam(
                type="message",
                role="developer",
                content=SYSTEM_SENKO_PROMPT.read_text(encoding="utf-8"),
            ),
            EasyInputMessageParam(
                type="message",
                role="assistant",
                content=MAIN_MEMORIES_PATH.read_text(encoding="utf-8"),
            )
        ]

        if is_program_starting and MAIN_MEMORIES_PATH.is_file():
            first_chunk.append(EasyInputMessageParam(
                type="message",
                role="assistant",
                content=NOTES_TO_NEXT_START_PATH.read_text(encoding="utf-8"),
            ))

        return first_chunk

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

    def get(self) -> ResponseInputParam:
        return [
            item
            for chunk in self._history
            for item in chunk
        ]

    async def compressing(self):
        self._history.pop(0)
        old_summary_chunk: ResponseInputParam = self._history.pop(0)

        compressed: list[ResponseInputParam] = []
        while self.size() >= COMPRESS_TO_SIZE:
            compressed.append(self._history.pop(0))

        print(f"Compressed {len(compressed)} chunks")

        response: Response = await self.summary_client.responses.create(
            model=SUMMARY_MODEL,
            input=get_text_from_history_part([old_summary_chunk, *compressed]),
            reasoning=SUMMARY_REASONING,
            stream=False,
        )

        new_summary_chunk: ResponseInputParam = [
            EasyInputMessageParam(
                type="message",
                role="assistant",
                content=response.output_text,
            )
        ]

        self._history = [
            self.create_first_chunk(),
            new_summary_chunk,
            *self._history
        ]

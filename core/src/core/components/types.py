from senko_protocol.path import BASE_DIR
from core.components.path import SYSTEM_SENKO_PROMPT
from openai.types.responses import ResponseInputParam, EasyInputMessageParam, ResponseInputItemParam
from openai import AsyncOpenAI
from openai.types.shared_params import Reasoning, ResponsesModel
from openai.types.responses import Response
from typing import overload, Self
from pathlib import Path
import aiosqlite
import tiktoken
import json


MAX_TOKEN_SIZE = 240_000
COMPRESS_TO_SIZE = 130_000

MAIN_MEMORIES_PATH = Path("/home/Senka/main_memories.md")
NOTES_TO_NEXT_START_PATH = Path("/home/Senka/notes_to_next_start.md")
HISTORY_DB_PATH = Path("/home/Senka/memory/history.db")

SUMMARY_MODEL: ResponsesModel = "gpt-5.6-luna"
SUMMARY_REASONING: Reasoning = Reasoning(
    effort="none",
)


def get_text_from_history_part(history_part: list[ResponseInputParam]) -> str:
    return json.dumps(history_part, ensure_ascii=False)


class History:
    def __init__(self):
        self._history: list[ResponseInputParam] = [self.create_first_chunk(is_program_starting=True)]
        self._encoding = tiktoken.encoding_for_model("gpt-5.6-luna")

        self.summary_client: AsyncOpenAI = AsyncOpenAI()

        self._db: aiosqlite.Connection | None = None
        self._chunk_id: int = 0
        self._position: int = 0

    async def load(self) -> Self:
        self._db = await aiosqlite.connect(HISTORY_DB_PATH)

        assert self._db is not None

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                chunk_id INTEGER NOT NULL,
                position INTEGER NOT NULL UNIQUE,
                data TEXT NOT NULL
            )
        """)

        await self._db.commit()

        async with self._db.execute(
                "SELECT chunk_id, position, data FROM messages ORDER BY position"
        ) as cursor:
            rows = list(await cursor.fetchall())

        self._history = [self.create_first_chunk()]

        previous_chunk_id: int | None = None

        chunk_id: int
        position: int
        data: str
        for chunk_id, position, data in rows:
            if chunk_id != previous_chunk_id:
                self._history.append([])
                previous_chunk_id = chunk_id

            self._history[-1].append(json.loads(data))

        if rows:
            self._chunk_id = rows[-1][0]
            self._position = rows[-1][1] + 1
        else:
            self._chunk_id = 0
            self._position = 0

        self._history.append([])
        self._chunk_id += 1

        return self

    async def close(self) -> None:
        database: aiosqlite.Connection | None = self._db
        self._db = None

        try:
            if database is not None:
                await database.close()
        finally:
            await self.summary_client.close()

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

    async def add(self, message: ResponseInputItemParam):
        self._history[-1].append(message)

        assert self._db is not None

        await self._db.execute(
            """
            INSERT INTO messages (chunk_id, position, data)
            VALUES (?, ?, ?)
            """,
            (
                self._chunk_id,
                self._position,
                json.dumps(message, ensure_ascii=False),
            ),
        )

        await self._db.commit()
        self._position += 1

    async def open_new_chunk(self):
        if self.size() > MAX_TOKEN_SIZE:
            await self.compressing()

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

        await self._save_history()

    async def _save_history(self):
        rows: list[tuple[int, int, str]] = []
        position: int = 0

        assert self._db is not None

        for chunk_id, chunk in enumerate(self._history[1:]):
            for message in chunk:
                rows.append((
                    chunk_id,
                    position,
                    json.dumps(message, ensure_ascii=False),
                ))
                position += 1

        await self._db.execute("BEGIN IMMEDIATE")

        try:
            await self._db.execute("DELETE FROM messages")

            await self._db.executemany(
                """
                INSERT INTO messages (chunk_id, position, data)
                VALUES (?, ?, ?)
                """,
                rows,
            )

            await self._db.commit()

        except Exception:
            await self._db.rollback()
            raise

        self._position = position
        self._chunk_id = len(self._history) - 2

        await self._db.commit()

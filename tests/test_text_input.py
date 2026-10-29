import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from listener import TextInput


class TextInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_hear_continues_after_empty_responses(self):
        # Avoid starting the unrelated background answer consumer.
        text_input = TextInput.__new__(TextInput)
        text_input.text_queue = asyncio.Queue()
        text_input.tts_queue = asyncio.Queue()
        text_input.buffer = ""
        text_input.content = []
        text_input.context = ""
        text_input.client = SimpleNamespace(chat=AsyncMock(side_effect=[
            SimpleNamespace(message=SimpleNamespace(content="")),
            SimpleNamespace(message=SimpleNamespace(content=None)),
            SimpleNamespace(message=SimpleNamespace(
                content='{"action":"add","text":"Hello","is_complete":true}',
            )),
        ]))
        for text in ("first", "second", "third"):
            text_input.text_queue.put_nowait(text)

        worker = asyncio.create_task(text_input.hear())
        try:
            answer = await asyncio.wait_for(text_input.tts_queue.get(), timeout=1)
            self.assertEqual(answer, "Hello ")
            self.assertEqual(text_input.client.chat.await_count, 3)
            self.assertFalse(worker.done())
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)

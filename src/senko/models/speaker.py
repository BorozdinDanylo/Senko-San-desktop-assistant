from senko import SENKO_PROMPT, SENKO_MODEL_NAME, SENKO_TEMPERATURE, SENKO_THINK_MODE
from typing import List
from ollama import AsyncClient, Message
import asyncio


class Speaker:
    def __init__(self, text_analiz: asyncio.Queue[str], tts_queue: asyncio.Queue[str]):
        self.text_analiz = text_analiz
        self.tts_queue = tts_queue

        self.content: List[Message] = []
        self.context: str = ""

        self.client: AsyncClient = AsyncClient()

    def update_content(self, role: str, content: str):
        self.content.append(
            Message(
                role=role,
                content=content,
            )
        )

    def get_message(self) -> List[Message]:
        return [
            SENKO_PROMPT,
            *self.content,
        ]

    async def live(self):
        while True:
            text = await self.text_analiz.get()
            self.update_content("user", text)
            messages = self.get_message()

            response = await self.client.chat(
                model=SENKO_MODEL_NAME,
                messages=messages,
                think=SENKO_THINK_MODE,
                stream=False,
                keep_alive="1m",
                options={
                    "temperature": SENKO_TEMPERATURE,
                },
            )

            answer = response.message.content
            if answer:
                self.update_content(response.message.role, answer)
                await self.tts_queue.put(answer)



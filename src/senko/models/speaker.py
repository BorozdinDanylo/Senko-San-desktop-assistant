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
            Message(
                role="system",
                content=SENKO_PROMPT,
            ),
            *self.content,
        ]

    async def live(self):
        await self.preload_model()
        while True:
            text = await self.text_analiz.get()
            self.update_content("user", text)
            messages = self.get_message()

            stream = await self.client.chat(
                model=SENKO_MODEL_NAME,
                messages=messages,
                think=SENKO_THINK_MODE,
                stream=True,
                keep_alive=-1,
                options={
                    "temperature": SENKO_TEMPERATURE,
                },
            )

            answer = ""
            buffer = ""
            async for chunk in stream:
                text = chunk.message.content or ""
                buffer += text

                if any(char in buffer for char in ".!?…"):
                    print(buffer)
                    await self.tts_queue.put(buffer.strip())
                    answer += f"{buffer.strip()} "
                    buffer = ""
                if chunk["done"]:
                    print()
                    print(f"Total:       {chunk['total_duration'] / 1e9:.2f}s")
                    print(f"Loading:     {chunk['load_duration'] / 1e9:.2f}s")
                    print(f"Prompt eval: {chunk['prompt_eval_duration'] / 1e9:.2f}s")
                    print(f"Generation:  {chunk['eval_duration'] / 1e9:.2f}s")
            if buffer.strip():
                print(buffer)
                await self.tts_queue.put(buffer.strip())
                answer += buffer.strip()

            self.update_content("chat", answer)

    async def preload_model(self):
        await self.client.chat(
            model=SENKO_MODEL_NAME,
            messages=[],
            keep_alive=-1,
        )
        print("Senko-San is ready")


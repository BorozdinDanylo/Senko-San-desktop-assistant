from senko import SENKO_PROMPT, SENKO_MODEL_NAME, SENKO_TEMPERATURE, SENKO_THINK_MODE, NewMessage
from pipeline.events_control import EventManager
from typing import List, Callable, Dict, Any, Coroutine
from ollama import AsyncClient, Message, ChatResponse
import asyncio
import emoji


class Speaker:
    def __init__(self, text_analiz: asyncio.Queue[str], tts_queue: asyncio.Queue[str], tools: Dict[str, Callable[..., Coroutine[Any, Any, str]]]):
        self.text_analiz = text_analiz
        self.tts_queue = tts_queue

        self.content: List[Message] = []
        self.tools = tools
        self.context: str = ""

        self.client: AsyncClient = AsyncClient()

    def update_content(self, role: str, content: str):
        if content == "":
            return

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
                tools=list(self.tools.values()),
                keep_alive=-1,
                options={
                    "temperature": SENKO_TEMPERATURE,
                    "num_ctx": 4096
                },
            )

            EventManager.stop_talking()
            self.update_content("assistant", NewMessage.get_message())

            buffer = ""
            tool_calls: List[Message.ToolCall] = []
            async for chunk in stream:
                _tool_calls = chunk.message.tool_calls
                if _tool_calls:
                    tool_calls.extend(_tool_calls)

                text = emoji.replace_emoji(chunk.message.content or "")
                buffer += text

                if any(char in buffer for char in ".!?…"):
                    print(buffer)
                    await self.tts_queue.put(buffer)
                    buffer = ""
                if chunk["done"]:
                    print()
                    print(f"Total:       {chunk['total_duration'] / 1e9:.2f}s")
                    print(f"Loading:     {chunk['load_duration'] / 1e9:.2f}s")
                    print(f"Prompt eval: {chunk['prompt_eval_duration'] / 1e9:.2f}s")
                    print(f"Generation:  {chunk['eval_duration'] / 1e9:.2f}s")
            if buffer:
                print(buffer)
                await self.tts_queue.put(buffer)

            if tool_calls:
                tool_answers = await self.start_tools(tool_calls)

                for tool_answer in tool_answers:
                    self.update_content("tool", tool_answer)

                print("Recalling Senko...")
                await self.text_analiz.put("")

            answer: str = NewMessage.get_message()

            self.update_content("assistant", answer)
            await EventManager.add_answer(answer)

    async def start_tools(self, tool_calls: List[Message.ToolCall]) -> List[str]:
        results: List[str] = []
        if not tool_calls:
            return []

        for call in tool_calls:
            try:
                func = self.tools[call.function.name]
            except KeyError:
                continue

            print(f"{call.function.name}({dict(**call.function.arguments)})")
            results.append(await func(**call.function.arguments))

        print(results)
        return results



    async def preload_model(self):
        await self.client.chat(
            model=SENKO_MODEL_NAME,
            messages=[],
            keep_alive=-1,
        )
        print("Senko-San is ready")


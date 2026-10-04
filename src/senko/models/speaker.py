from senko import SENKO_PROMPT, SENKO_MODEL_NAME, SENKO_TEMPERATURE, SENKO_THINK_MODE
from typing import List, Callable, Dict, Any, Coroutine
from ollama import AsyncClient, Message, ChatResponse
import asyncio
import emoji


class Speaker:
    def __init__(self, text_analiz: asyncio.Queue[str], tts_queue: asyncio.Queue[str], tools: Dict[str, Callable[..., Coroutine[Any, Any, str]]], on_response: Callable[[str], None], stop_talking: Callable[..., None]):
        self.text_analiz = text_analiz
        self.tts_queue = tts_queue
        self.on_response = on_response
        self.stop_talking = stop_talking

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

            self.stop_talking()

            answer = ""
            buffer = ""
            tool_calls: List[Message.ToolCall] = []
            async for chunk in stream:
                _tool_calls = chunk.message.tool_calls
                if _tool_calls:
                    tool_calls.extend(_tool_calls)

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

            if tool_calls:
                tool_answers = await self.start_tools(tool_calls)

                for tool_answer in tool_answers:
                    self.update_content("tool", tool_answer)

                print("Recalling Senko...")
                await self.text_analiz.put("")

            answer = emoji.replace_emoji(answer, "")

            self.update_content("assistant", answer)
            self.on_response(answer)

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


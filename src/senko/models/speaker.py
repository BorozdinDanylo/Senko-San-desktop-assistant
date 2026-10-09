from senko import SENKO_PROMPT, SENKO_MODEL_NAME, SENKO_REASONING_MODE, NewMessage
from pipeline.events_control import EventManager
from typing import Callable, Any, Coroutine, Literal, cast
from openai import AsyncOpenAI, AsyncStream
from openai.types.responses import (
    ResponseInputItemParam,
    ResponseInputParam,
    EasyInputMessageParam,
    ResponseStreamEvent,
    ResponseOutputItemDoneEvent,
    ResponseTextDeltaEvent,
    ResponseFunctionToolCall,
    ResponseReasoningItemParam,
    ResponseReasoningItem,
)
import asyncio
import json
import emoji


type ToolFunction = dict[str, Callable[..., Coroutine[Any, Any, str]]]


class Speaker:
    def __init__(
            self,
            text_analiz: asyncio.Queue[str],
            tts_queue: asyncio.Queue[str],
            tools: ToolFunction,
    ):

        self.text_analiz = text_analiz
        self.tts_queue = tts_queue

        self.history: ResponseInputParam = []
        self.tools = tools
        self.context: str = ""

        self.client: AsyncOpenAI = AsyncOpenAI()

    def update_content(
            self,
            role: Literal["user", "assistant"],
            content: str,
    ):

        if content == "":
            return

        new_content: EasyInputMessageParam = {
            "role": role,
            "content": content,
        }

        self.history.append(new_content)

    @property
    def prompt(self) -> ResponseInputItemParam:
        prompt: ResponseInputItemParam = {
            "role": "system",
            "content": SENKO_PROMPT,
        }

        return prompt

    def get_message(self) -> ResponseInputParam:
        return [
            self.prompt,
            *self.history,
        ]

    async def live(self):
        print("Senko-San is ready")
        while True:
            text = await self.text_analiz.get()
            self.update_content("user", text)
            messages = self.get_message()

            stream: AsyncStream[ResponseStreamEvent] = await self.client.responses.create(
                model=SENKO_MODEL_NAME,
                input=messages,
                reasoning=SENKO_REASONING_MODE,
                stream=True,
            )

            EventManager.stop_talking()
            self.update_content("assistant", NewMessage.get_message())

            buffer = ""
            tool_calls: list[ResponseFunctionToolCall] = []

            async for event in stream:
                match event.type:
                    case "response.output_text.delta":
                        delta_event: ResponseTextDeltaEvent = cast(ResponseTextDeltaEvent, event)

                        text = emoji.replace_emoji(delta_event.delta)
                        buffer += text

                        if any(char in buffer for char in ".!?…"):
                            print(buffer)
                            await self.tts_queue.put(buffer)
                            buffer = ""

                    case "response.output_item.done":
                        done_event: ResponseOutputItemDoneEvent = cast(ResponseOutputItemDoneEvent, event)
                        if done_event.item.type == "function_call":
                            tool_call: ResponseFunctionToolCall = cast(ResponseFunctionToolCall, done_event.item)
                            tool_calls.append(tool_call)
                            self.history.append({
                                "type": "function_call",
                                "call_id": tool_call.call_id,
                                "name": tool_call.name,
                                "arguments": tool_call.arguments,
                            })

                        elif done_event.item.type == "reasoning":
                            reasoning: ResponseReasoningItem = cast(ResponseReasoningItem, done_event.item)

                            reasoning_param: ResponseReasoningItemParam = cast(
                                ResponseReasoningItemParam,
                                reasoning.model_dump(exclude_none=True),
                            )

                            self.history.append(reasoning_param)

                    case "response.completed":
                        print()

            if buffer:
                print(buffer)
                await self.tts_queue.put(buffer)

            if tool_calls:
                tool_answers = await self.start_tools(tool_calls)

                for tool_call, tool_answer in zip(tool_calls, tool_answers):
                    self.history.append({
                        "type": "function_call_output",
                        "call_id": tool_call.call_id,
                        "output": tool_answer,
                    })

                print("Recalling Senko...")
                await self.text_analiz.put("")

            answer = NewMessage.get_message()

            self.update_content("assistant", answer)
            await EventManager.add_answer(answer)

    async def start_tools(self, tool_calls: list[ResponseFunctionToolCall]) -> list[str]:
        results: list[str] = []
        if not tool_calls:
            return []

        for call in tool_calls:
            try:
                func = self.tools[call.name]
            except KeyError:
                continue

            print(f"{call.name}({json.loads(call.arguments)})")
            results.append(await func(*json.loads(call.arguments)))

        print(results)
        return results





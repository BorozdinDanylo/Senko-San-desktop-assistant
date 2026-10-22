from senko import SENKO_PROMPT, SENKO_MODEL_NAME, SENKO_REASONING_MODE, NewMessage
from pipeline.events_control import EventManager
from tools import Tool
from typing import Literal, cast
from openai import AsyncOpenAI, AsyncStream
from openai.types.responses.response_input_param import FunctionCallOutput
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
import emoji


class Speaker:
    def __init__(
            self,
            text_analiz: asyncio.Queue[str],
            tts_queue: asyncio.Queue[str],
    ):

        self.text_analiz = text_analiz
        self.tts_queue = tts_queue

        self.history: ResponseInputParam = []
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
            EventManager.stop_talking()
            await asyncio.sleep(0)  # Drain queued speech before the next response.
            previous_answer = NewMessage.get_message()
            self.update_content("assistant", previous_answer)
            self.update_content("user", text)
            messages = self.get_message()

            stream: AsyncStream[ResponseStreamEvent] = await self.client.responses.create(
                model=SENKO_MODEL_NAME,
                input=messages,
                tools=Tool.tools_shamas,
                tool_choice="auto",
                reasoning=SENKO_REASONING_MODE,
                stream=True,
            )

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
                            NewMessage.add_text(buffer)
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
                NewMessage.add_text(buffer)
                await self.tts_queue.put(buffer)

            if tool_calls:
                tool_answers = await self.start_tools(tool_calls)

                if len(tool_calls) != len(tool_answers):
                    raise RuntimeError(
                        f"Tool calls: {len(tool_calls)}, "
                        f"Tool answers: {len(tool_answers)}"
                    )

                self.history.extend(tool_answers)

                print("Recalling Senko...")
                await self.text_analiz.put("")

            # Give the transcription router current context without resetting playback tracking.
            answer = NewMessage.get_message(clear=False)
            if answer:
                await EventManager.add_answer(answer)

    @staticmethod
    async def start_tools(tool_calls: list[ResponseFunctionToolCall]) -> list[FunctionCallOutput]:
        results: list[FunctionCallOutput] = []
        if not tool_calls:
            return []

        for call in tool_calls:
            results.append(await Tool.execute(call))

        print(results)
        return results





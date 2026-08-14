from typing import List, Optional
from listener.config.llm import MODEL, THINK_MODE, RouterResult, TEMPERATURE, MAX_CONTEXT_SIZE, SYSTEM_PROMPT, PERHAPS_ACTION
from ollama import AsyncClient, Message


class TextInput:
    def __init__(self):
        self.buffer: str = ""
        self.context: str = ""
        self.content: List[Message] = []

        self.client: AsyncClient = AsyncClient()

    def update_content(self, text: str):
        self.content.append(
            Message(
                role="user",
                content=text,
            )
        )
        if len(self.content) > MAX_CONTEXT_SIZE:
            self.content = self.content[len(self.content) - MAX_CONTEXT_SIZE:]

    def update_buffer(self, action: PERHAPS_ACTION, text: Optional[str]):
        match action:
            case "add":
                self.buffer += f"{text or ""} "
            case "clear":
                self.buffer = ""
                print("buffer is clear")

    def get_messages(self, text) -> List[Message]:
        return [
            Message(
                role="system",
                content=SYSTEM_PROMPT,
            ),
            *self.content,
            Message(
                role="user",
                content=f"""
                    Current request buffer:
                    {self.buffer}

                    New transcription:
                    {text}
                """,
            )
        ]

    async def hear(self, text: str):
        messages = self.get_messages(text)

        response = await self.client.chat(
            model=MODEL,
            messages=messages,
            think=THINK_MODE,
            format=RouterResult.model_json_schema(),
            stream=False,
            keep_alive="1m",
            options={
                "temperature": TEMPERATURE,
            },
        )

        self.update_content(text)
        self.content.append(response.message)
        content = response.message.content

        if not content:
            return

        resalt = RouterResult.model_validate_json(content)
        self.update_buffer(resalt.action, resalt.text)

        print(content)




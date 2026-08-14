from typing import List, Optional
from whisper.config.llm import MODEL, THINK_MODE,RouterResult, TEMPERATURE, MAX_CONTEXT_SIZE, SYSTEM_PROMPT, PERHAPS_ACTION
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



async def main():
    test_inputs = [
        # Просте пряме звернення
        "Сенко, відкрий PyCharm",

        # Продовження попереднього запиту
        "і відкрий там проєкт inventory",

        # Слова-паразити / жива мова
        "Сенко, коротше, цей, відкрий мені, будь ласка, браузер",

        # Не звернення до Senko
        "Та ні, постав його краще сюди, я потім сам розберусь",

        # Думки вголос
        "Так, треба буде ще сьогодні закінчити таблицю...",

        # Звернення + незакінчена команда
        "Сенко, можеш відкрити цей...",

        # Продовження після паузи
        "як його... PyCharm",

        # Самовиправлення
        "Сенко, відкрий Firefox... ні, стоп, краще Chrome",

        # Скасування
        "А, ні, Сенку, забудь, не треба",

        # Можлива помилка STT
        "Синку відкрий пай чарм і проект інвентарі",

        # Звернення до іншої людини
        "Макс, відкрий, будь ласка, браузер",

        # Senko згадується, але це не команда їй
        "Я вчора налаштовував Сенку, щоб вона запускала програми",

        # Команда з технічними термінами
        "Сенко, відкрий термінал і запусти git status у проєкті inventory",

        # Закінчений запит без явного імені — важливо при активному buffer
        "і після цього відкрий останній коміт",

        # Різка зміна думки
        "Сенко, відкрий термінал... хоча ні, нічого не роби",
    ]

    wisper = TextInput()
    for text in test_inputs:
        await wisper.hear(text)

    print(wisper.buffer)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())

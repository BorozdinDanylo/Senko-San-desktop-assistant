from typing import Literal
from pathlib import Path
from openai.types.shared_params import Reasoning, ChatModel


BASE_DIR = Path(__file__).resolve().parent.parent.parent
SENKO_PROMPT_FILE = BASE_DIR / "senko_prompt.md"

with open(SENKO_PROMPT_FILE, "r", encoding="utf-8") as f:
    SENKO_PROMPT = f.read()

# Senko-San config
type ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]

SENKO_MODEL_NAME: ChatModel = "gpt-5.6-luna"
SENKO_THINK_MODE: ReasoningEffort = "low"
SENKO_TEMPERATURE = .7

SENKO_REASONING_MODE: Reasoning = {
    "effort": SENKO_THINK_MODE,
}



class NewMessage:
    generation: int = 0
    full_text: str = ""
    spoken_text: str = ""

    @classmethod
    def add_text(cls, text: str):
        cls.full_text += f"{text} "
        print(text)

    @classmethod
    def spoken(cls, text: str):
        if not cls.full_text[len(cls.spoken_text):].startswith(f"{text} "):
            return

        cls.spoken_text += f"{text} "
        print(text)

    @classmethod
    def clear(cls):
        cls.generation += 1
        cls.full_text = ""
        cls.spoken_text = ""

    @classmethod
    def get_message(cls, *, clear: bool = True) -> str:
        if cls.full_text == "":
            return ""

        unspoken_text = cls.full_text[len(cls.spoken_text):] if cls.full_text.startswith(cls.spoken_text) else cls.full_text

        message: str = f"""
            Spoken text:
            {cls.spoken_text.strip() or "<empty>"}
            Unspoken text:
            {unspoken_text.strip() or "<empty>"}
        """

        if clear:
            cls.clear()

        return message

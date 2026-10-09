from typing import Literal
from pathlib import Path
from openai.types.shared_params import Reasoning, ChatModel


BASE_DIR = Path(__file__).resolve().parent.parent.parent
SENKO_PROMPT_FILE = BASE_DIR / "senko_prompt.md"

with open(SENKO_PROMPT_FILE, "r") as f:
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
    full_text: str = ""
    spoken_text: str = ""

    @classmethod
    def add_text(cls, text: str):
        cls.full_text += f"{text} "
        print(text)

    @classmethod
    def spoken(cls, text: str):
        if text not in cls.full_text:
            return

        cls.spoken_text += f"{text} "
        print(text)

    @classmethod
    def clear(cls):
        cls.full_text = ""
        cls.spoken_text = ""

    @classmethod
    def get_message(cls) -> str:
        if cls.full_text == "":
            return ""

        unspoken_text = cls.full_text.replace(cls.spoken_text, "", 1)

        message: str = f"""
            Spoken text:
            {cls.spoken_text or "<empty>"}
            Unspoken text:
            {unspoken_text or "<empty>"}
        """

        cls.clear()

        return message

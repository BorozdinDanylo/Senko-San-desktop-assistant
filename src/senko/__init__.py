from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent
SENKO_PROMPT_FILE = BASE_DIR / "senko_prompt.txt"

with open(SENKO_PROMPT_FILE, "r") as f:
    SENKO_PROMPT = f.read()

# Senko-San config
SENKO_MODEL_NAME = "qwen3:14b"
SENKO_THINK_MODE = False
SENKO_TEMPERATURE = .9


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

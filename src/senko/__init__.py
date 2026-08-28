from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent
SENKO_PROMPT_FILE = BASE_DIR / "senko_prompt.txt"

with open(SENKO_PROMPT_FILE, "r") as f:
    SENKO_PROMPT = f.read()

# Senko-San config
SENKO_MODEL_NAME = "qwen3:14b"
SENKO_THINK_MODE = "low"
SENKO_TEMPERATURE = .9

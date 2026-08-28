from typing import Literal, Optional
from pydantic import BaseModel
from listener.config.path import SYSTEM_PROMPT_FILE


MODEL = "qwen3:14b"
THINK_MODE = False
TEMPERATURE = 0
MAX_CONTEXT_SIZE = 20

with open(SYSTEM_PROMPT_FILE) as f:
    SYSTEM_PROMPT = f.read()

PERHAPS_ACTION = Literal["skip", "add", "update", "send", "clear"]


class RouterResult(BaseModel):
    action: PERHAPS_ACTION
    text: Optional[str] = None

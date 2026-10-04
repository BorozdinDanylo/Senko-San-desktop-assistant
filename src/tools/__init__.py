from typing import Any, Dict, TypeVar
from collections.abc import Callable


F = TypeVar("F", bound=Callable[..., Any])

def tool(fun: F) -> F:
    setattr(fun, "__tool__", True)
    return fun

class Tool:
    def __init__(self):
        self.tools: Dict[str, Callable[..., Any]] = {
            name: getattr(self, name)
            for name in dir(self)
            if callable(getattr(self, name))
            and getattr(getattr(self, name), "__tool__", False)
        }



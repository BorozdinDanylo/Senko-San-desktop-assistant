from .tool_shema import ToolShema, Parameter, Properties
from pydantic import TypeAdapter, Field
from pydantic.fields import FieldInfo
from collections.abc import Callable, Awaitable
from typing import get_type_hints, Annotated, Any, get_args, get_origin
import inspect

type F = Callable[..., Awaitable[str]]
type FDict = dict[str, F]

FDictAdapter: TypeAdapter[FDict] = TypeAdapter(FDict)

type Arg[T] = Annotated[
    T,
    Field(description="A tool argument"),
]

class Tool:
    tools_shamas: list[dict[str, Any]] = []
    tools: FDict = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)

        prefix: str = cls.__name__.removesuffix("Tool").lower()

        tools: FDict = {
            f"{prefix}_{name}": method
            for name in dir(cls)
            if callable(method := getattr(cls, name))
            and getattr(method, "__tool__", False)
        }

        cls.tools.update(FDictAdapter.validate_python(tools))

        for tool in cls.tools.values():
            cls.tools_shamas.append(cls.tool_to_shema(tool, prefix))

    @staticmethod
    def tool(fun: F) -> F:
        setattr(fun, "__tool__", True)
        return fun

    @staticmethod
    def tool_to_shema(fun: F, prefix: str) -> dict[str, Any]:
        hints: dict[str, Arg[Any]] = get_type_hints(fun, include_extras=True)

        new_tool_shema: ToolShema = ToolShema(
            name=f"{prefix}_{fun.__name__}",
            description=inspect.cleandoc(fun.__doc__),
            parameters=Parameter(),
        )

        for arg_name, arg in hints.items():
            if arg_name == "return":
                continue
            elif get_origin(arg) is Annotated:
                base_type, *metadata = get_args(arg)

                if isinstance(metadata[0], FieldInfo):
                    field: FieldInfo = metadata[0]
                else:
                    raise TypeError("All params must be annotated with Field")

                if not field.description:
                    raise TypeError("All params must be with description")

                new_tool_shema.parameters.properties.update({
                    arg_name: Properties(
                        type=TypeAdapter(base_type).json_schema()["type"],
                        description=inspect.cleandoc(field.description),
                    )
                })

                new_tool_shema.parameters.required.append(arg_name)
            else:
                raise TypeError("All params must be annotated")

        return new_tool_shema.model_dump()

    @classmethod
    def initialize(cls):
        pass

    @staticmethod
    def initialize_class(cls: type[Tool]):
        cls.initialize()
        return cls





from .tool_shema import ToolShema, Parameter, Properties
from pydantic import TypeAdapter, Field
from pydantic.fields import FieldInfo
from openai.types.responses import ResponseFunctionToolCall, FunctionToolParam
from openai.types.responses.response_input_param import FunctionCallOutput
from collections.abc import Callable, Awaitable
from typing import get_type_hints, Annotated, Any, get_args, get_origin
import inspect
import json

type F = Callable[..., Awaitable[str]]
type FDict = dict[str, F]

FDictAdapter: TypeAdapter[FDict] = TypeAdapter(FDict)
FunctionToolParamAdapter: TypeAdapter[FunctionToolParam] = TypeAdapter(FunctionToolParam)

type Arg[T] = Annotated[
    T,
    Field(description="A tool argument"),
]
type Args = dict[str, Arg[Any]]


class Tool:
    tools_shamas: list[FunctionToolParam] = []
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

        for tool in tools.values():
            cls.tools_shamas.append(cls.tool_to_shema(tool, prefix))

    @staticmethod
    def tool(fun: F) -> F:
        setattr(fun, "__tool__", True)
        return fun

    @staticmethod
    def tool_to_shema(fun: F, prefix: str) -> FunctionToolParam:
        hints: Args = get_type_hints(fun, include_extras=True)

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

                schema = TypeAdapter(base_type).json_schema()

                if "anyOf" in schema:
                    variants = schema["anyOf"]

                    if all(set(item) == {"type"} for item in variants):
                        schema["type"] = [item["type"] for item in variants]
                        del schema["anyOf"]

                new_tool_shema.parameters.properties.update({
                    arg_name: Properties(
                        type=schema["type"],
                        description=inspect.cleandoc(field.description),
                    )
                })

                new_tool_shema.parameters.required.append(arg_name)
            else:
                raise TypeError("All params must be annotated")

        return FunctionToolParamAdapter.validate_python(new_tool_shema.model_dump())

    @classmethod
    async def execute(cls, tool_call: ResponseFunctionToolCall) -> FunctionCallOutput:
        try:
            func: F = cls.tools[tool_call.name]
            args: Args = json.loads(tool_call.arguments)

            result: str = await func(**args)

            output: dict[str, Any] = {
                "success": True,
                "result": result,
            }
        except Exception as e:
            output: dict[str, Any] = {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
            }

        return FunctionCallOutput(
            call_id=tool_call.call_id,
            type="function_call_output",
            output=json.dumps(output),
        )

    @classmethod
    def initialize(cls):
        pass

    @staticmethod
    def initialize_class(cls: type[Tool]):
        cls.initialize()
        return cls





from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Properties(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    type: str
    description: str


class Parameter(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    type: Literal["object"] = "object"
    properties: dict[str, Properties] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)
    additionalProperties: bool = False


class ToolShema(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    type: Literal["function"] = "function"
    name: str
    description: str
    parameters: Parameter
    strict: bool = True


